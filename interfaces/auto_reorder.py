"""
자동 재주문 발주 프로그램
Team 발닦고디비자라 - 파리바게트 지점 재고 및 판매 관리 시스템

이 파일은 사용자 인터페이스 기능 설명서의 "자동 재주문 발주 프로그램"을 구현한
백그라운드 배치형 Python 프로그램입니다.

실행 방법:
    프로젝트 최상위 폴더에서 실행
    python3 interfaces/auto_reorder.py

안전 모드:
    기본 실행은 DRY-RUN 미리보기 모드입니다.
    재고 부족 항목을 찾고 어떤 발주가 생성될지 보여주지만 DB에는 INSERT/UPDATE를 하지 않습니다.

실제 DB 반영:
    1) 일반 실행 후 마지막 확인 질문에서 y 입력
       python3 interfaces/auto_reorder.py

    2) 명령행 옵션으로 바로 실행 모드 진입
       python3 interfaces/auto_reorder.py --execute

주요 기능:
    - 전 매장의 재고 부족 항목 스캔
    - 보유.재고수량 < 보유.최소재고기준 항목 탐색
    - 동일 매장/상품에 대해 이미 대기 상태의 발주가 있으면 중복 발주 방지
    - 공급 가능한 업체를 공급 테이블에서 자동 선택
    - 같은 매장 + 같은 공급업체 단위로 발주 그룹화
    - 발주 및 발주상세 자동 생성
    - 실행 결과와 스킵 사유 출력
    - logs/auto_reorder_log.txt에 실행 로그 기록

관련 테이블:
    보유, 상품, 브랜드, 공급, 공급업체, 발주, 발주상세
"""

import argparse
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path


DEFAULT_DB_NAMES = ["파리바게트.db", "paris_baguette.db", "database.db"]


class AutoReorderProgram:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.conn = None
        self.created_orders = []
        self.skipped_items = []
        self.plan_groups = {}

    def connect(self):
        if not self.db_path.exists():
            raise FileNotFoundError(f"DB 파일을 찾을 수 없습니다: {self.db_path}")

        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.validate_required_tables()
        print(f"\nDB 접속 완료: {self.db_path}")

    def close(self):
        if self.conn:
            self.conn.close()
            print("DB 연결을 종료했습니다.")

    def validate_required_tables(self):
        required = {"보유", "상품", "브랜드", "공급", "공급업체", "발주", "발주상세"}
        rows = self.fetch_all(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%';
            """
        )
        existing = {row["name"] for row in rows}
        missing = sorted(required - existing)

        if missing:
            raise RuntimeError("필수 테이블이 없습니다: " + ", ".join(missing))

    def fetch_all(self, sql, params=()):
        if self.conn is None:
            raise RuntimeError("DB 연결이 없습니다.")
        cur = self.conn.execute(sql, params)
        return cur.fetchall()

    def fetch_one(self, sql, params=()):
        if self.conn is None:
            raise RuntimeError("DB 연결이 없습니다.")
        cur = self.conn.execute(sql, params)
        return cur.fetchone()

    def scan_low_stock_items(self):
        rows = self.fetch_all(
            """
            SELECT
                h.지점명,
                h.상품코드,
                p.이름 AS 상품명,
                b.브랜드명,
                h.재고수량,
                h.최소재고기준,
                h.매장가격,
                p.가격 AS 기본가격,
                MIN(s.업체코드) AS 업체코드,
                sp.업체명
            FROM 보유 h
            JOIN 상품 p ON h.상품코드 = p.상품코드
            LEFT JOIN 브랜드 b ON p.브랜드코드 = b.브랜드코드
            LEFT JOIN 공급 s ON h.상품코드 = s.상품코드
            LEFT JOIN 공급업체 sp ON s.업체코드 = sp.업체코드
            WHERE h.재고수량 < h.최소재고기준
            GROUP BY
                h.지점명,
                h.상품코드,
                p.이름,
                b.브랜드명,
                h.재고수량,
                h.최소재고기준,
                h.매장가격,
                p.가격
            ORDER BY h.지점명, h.상품코드;
            """
        )

        candidates = []
        skipped = []

        for row in rows:
            store_name = row["지점명"]
            product_code = row["상품코드"]
            supplier_code = row["업체코드"]

            if supplier_code is None:
                skipped.append(
                    {
                        "지점명": store_name,
                        "상품코드": product_code,
                        "상품명": row["상품명"],
                        "현재재고": row["재고수량"],
                        "최소재고기준": row["최소재고기준"],
                        "스킵사유": "공급 가능 업체 없음",
                    }
                )
                continue

            if self.has_pending_order(store_name, product_code):
                skipped.append(
                    {
                        "지점명": store_name,
                        "상품코드": product_code,
                        "상품명": row["상품명"],
                        "현재재고": row["재고수량"],
                        "최소재고기준": row["최소재고기준"],
                        "스킵사유": "동일 매장/상품 대기 발주 존재",
                    }
                )
                continue

            min_stock = row["최소재고기준"]
            current_stock = row["재고수량"]
            order_qty = self.calculate_order_quantity(current_stock, min_stock)

            candidates.append(
                {
                    "지점명": store_name,
                    "상품코드": product_code,
                    "상품명": row["상품명"],
                    "브랜드명": row["브랜드명"],
                    "현재재고": current_stock,
                    "최소재고기준": min_stock,
                    "권장주문수량": order_qty,
                    "업체코드": supplier_code,
                    "업체명": row["업체명"],
                }
            )

        self.skipped_items = skipped
        return candidates

    def has_pending_order(self, store_name, product_code):
        row = self.fetch_one(
            """
            SELECT 1
            FROM 발주 o
            JOIN 발주상세 od ON o.발주번호 = od.발주번호
            WHERE o.지점명 = ?
              AND od.상품코드 = ?
              AND o.상태 = '대기'
            LIMIT 1;
            """,
            (store_name, product_code),
        )
        return row is not None

    @staticmethod
    def calculate_order_quantity(current_stock, min_stock):
        target_stock = min_stock * 2
        qty = target_stock - current_stock
        return max(qty, min_stock - current_stock, 1)

    def build_order_plan(self, candidates):
        groups = defaultdict(list)

        for item in candidates:
            key = (item["지점명"], item["업체코드"], item["업체명"])
            groups[key].append(item)

        self.plan_groups = dict(groups)
        return self.plan_groups

    def print_summary(self, candidates):
        print("\n" + "=" * 80)
        print("자동 재주문 스캔 결과")
        print("=" * 80)

        total_low_stock = len(candidates) + len(self.skipped_items)
        print(f"재고 부족 감지 항목 수: {total_low_stock}")
        print(f"발주 생성 가능 항목 수: {len(candidates)}")
        print(f"스킵 항목 수: {len(self.skipped_items)}")

        if candidates:
            print("\n[발주 생성 가능 항목]")
            print_dict_rows(candidates)

        if self.skipped_items:
            print("\n[스킵 항목]")
            print_dict_rows(self.skipped_items)

        groups = self.build_order_plan(candidates)

        print("\n[발주 생성 계획]")
        if not groups:
            print("생성할 발주가 없습니다.")
            return

        plan_rows = []
        for (store_name, supplier_code, supplier_name), items in groups.items():
            plan_rows.append(
                {
                    "지점명": store_name,
                    "업체코드": supplier_code,
                    "업체명": supplier_name,
                    "발주항목수": len(items),
                    "총주문수량": sum(item["권장주문수량"] for item in items),
                }
            )

        print_dict_rows(plan_rows)

    def execute_order_plan(self):
        if not self.plan_groups:
            print("생성할 발주 계획이 없습니다.")
            return []

        now = datetime.now()
        order_date = now.strftime("%Y-%m-%d")
        created_orders = []

        try:
            self.conn.execute("BEGIN IMMEDIATE;")

            for (store_name, supplier_code, supplier_name), items in self.plan_groups.items():
                order_no = self.generate_order_no(len(created_orders) + 1)

                self.conn.execute(
                    """
                    INSERT INTO 발주 (발주번호, 발주일자, 상태, 지점명, 업체코드)
                    VALUES (?, ?, '대기', ?, ?);
                    """,
                    (order_no, order_date, store_name, supplier_code),
                )

                for idx, item in enumerate(items, start=1):
                    self.conn.execute(
                        """
                        INSERT INTO 발주상세 (발주번호, 항목번호, 주문수량, 상품코드)
                        VALUES (?, ?, ?, ?);
                        """,
                        (order_no, idx, item["권장주문수량"], item["상품코드"]),
                    )

                created_orders.append(
                    {
                        "발주번호": order_no,
                        "발주일자": order_date,
                        "상태": "대기",
                        "지점명": store_name,
                        "업체코드": supplier_code,
                        "업체명": supplier_name,
                        "발주항목수": len(items),
                        "총주문수량": sum(item["권장주문수량"] for item in items),
                    }
                )

            self.conn.commit()

        except Exception:
            self.conn.rollback()
            raise

        self.created_orders = created_orders
        return created_orders

    def generate_order_no(self, sequence):
        while True:
            stamp = datetime.now().strftime("%y%m%d%H%M%S")
            order_no = f"RO{stamp}{sequence:03d}"

            exists = self.fetch_one(
                """
                SELECT 발주번호
                FROM 발주
                WHERE 발주번호 = ?;
                """,
                (order_no,),
            )

            if not exists:
                return order_no

    def print_created_orders(self, created_orders):
        print("\n" + "=" * 80)
        print("자동 재주문 발주 생성 결과")
        print("=" * 80)

        if not created_orders:
            print("생성된 발주가 없습니다.")
            return

        print_dict_rows(created_orders)

    def write_log(self, mode, candidates, created_orders):
        log_dir = Path.cwd() / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "auto_reorder_log.txt"

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = []
        lines.append("=" * 80)
        lines.append(f"실행시각: {now}")
        lines.append(f"실행모드: {mode}")
        lines.append(f"DB파일: {self.db_path}")
        lines.append(f"재고부족 감지 항목 수: {len(candidates) + len(self.skipped_items)}")
        lines.append(f"발주 생성 가능 항목 수: {len(candidates)}")
        lines.append(f"스킵 항목 수: {len(self.skipped_items)}")
        lines.append(f"생성된 발주 수: {len(created_orders)}")

        if created_orders:
            lines.append("\n[생성된 발주]")
            for order in created_orders:
                lines.append(
                    f"- {order['발주번호']} | {order['지점명']} | {order['업체코드']} | "
                    f"항목 {order['발주항목수']}개 | 수량 {order['총주문수량']}"
                )

        if self.skipped_items:
            lines.append("\n[스킵 항목]")
            for item in self.skipped_items:
                lines.append(
                    f"- {item['지점명']} | {item['상품코드']} | {item['상품명']} | "
                    f"{item['스킵사유']}"
                )

        lines.append("")

        with log_file.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print(f"\n실행 로그 저장 완료: {log_file}")


def print_dict_rows(rows, max_width=22):
    if not rows:
        print("조회 결과가 없습니다.")
        return

    headers = list(rows[0].keys())
    str_rows = []

    for row in rows:
        str_rows.append([format_cell(row.get(header), max_width) for header in headers])

    widths = []
    for idx, header in enumerate(headers):
        width = max(len(header), *(len(row[idx]) for row in str_rows))
        widths.append(min(width, max_width))

    header_line = " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers)))
    print("\n" + header_line)
    print("-" * len(header_line))

    for row in str_rows:
        print(" | ".join(row[i].ljust(widths[i]) for i in range(len(headers))))

    print(f"\n총 {len(rows)}행")


def format_cell(value, max_width):
    if value is None:
        text = "NULL"
    else:
        text = str(value)

    text = text.replace("\n", " ")
    if len(text) > max_width:
        return text[: max_width - 3] + "..."
    return text


def discover_db_paths():
    paths = []
    cwd = Path.cwd()

    try:
        script_dir = Path(__file__).resolve().parent
        project_root = script_dir.parent
    except NameError:
        project_root = cwd

    bases = [
        cwd,
        cwd / "data",
        project_root,
        project_root / "data",
    ]

    for base in bases:
        for name in DEFAULT_DB_NAMES:
            candidate = base / name
            if candidate.exists() and candidate not in paths:
                paths.append(candidate)

    return paths


def select_db_path():
    found = discover_db_paths()

    if found:
        print("자동으로 찾은 DB 파일:")
        for idx, path in enumerate(found, 1):
            print(f"{idx}. {path}")

        while True:
            raw = input("사용할 DB 번호 선택, Enter=1 > ").strip()
            if not raw:
                return str(found[0])

            try:
                index = int(raw)
            except ValueError:
                print("번호를 입력하세요.")
                continue

            if 1 <= index <= len(found):
                return str(found[index - 1])

            print("목록에 있는 번호를 입력하세요.")

    print("자동으로 DB 파일을 찾지 못했습니다.")
    print("예: 파리바게트.db 또는 data/파리바게트.db")
    return input("사용할 DB 파일 경로 > ").strip()


def parse_args():
    parser = argparse.ArgumentParser(
        description="파리바게트 지점 재고 및 판매 관리 시스템 자동 재주문 발주 프로그램"
    )
    parser.add_argument(
        "--db",
        help="사용할 SQLite DB 파일 경로. 생략하면 자동 탐색 후 선택합니다.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="미리보기 후 실제 발주 INSERT를 수행합니다. 생략하면 안전한 DRY-RUN 모드입니다.",
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="실행 로그 파일을 작성하지 않습니다.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print("자동 재주문 발주 프로그램 실행")
    print("기본 모드: DRY-RUN 미리보기. 확인 전까지 DB는 변경되지 않습니다.")

    db_path = args.db if args.db else select_db_path()

    if not db_path:
        print("DB 파일 경로가 입력되지 않아 종료합니다.")
        return

    program = AutoReorderProgram(db_path)

    try:
        program.connect()

        candidates = program.scan_low_stock_items()
        program.print_summary(candidates)

        created_orders = []
        mode = "DRY-RUN"

        if not candidates:
            print("\n발주 생성 가능한 항목이 없어 종료합니다.")
        else:
            should_execute = args.execute

            if not args.execute:
                print("\n현재는 안전한 DRY-RUN 미리보기 상태입니다.")
                print("실제 DB에 발주/발주상세를 생성하려면 아래 질문에 y를 입력해야 합니다.")
                confirm = input("자동 재주문 발주를 실제로 생성할까요? (y/N) > ").strip().lower()
                should_execute = confirm == "y"

            if should_execute:
                created_orders = program.execute_order_plan()
                program.print_created_orders(created_orders)
                mode = "EXECUTE"
            else:
                print("\n실제 발주 생성은 취소되었습니다. DB는 변경되지 않았습니다.")

        if not args.no_log:
            program.write_log(mode, candidates, created_orders)

    except sqlite3.Error as e:
        print(f"SQLite 오류: {e}")
    except Exception as e:
        print(f"오류: {e}")
    finally:
        program.close()


if __name__ == "__main__":
    main()
