"""
공급업체 공급 처리 CLI
Team 발닦고디비자라 - 파리바게트 지점 재고 및 판매 관리 시스템

이 파일은 사용자 인터페이스 기능 설명서의 "공급업체 공급 처리"를 구현한 CLI 프로그램입니다.
공급업체 담당자가 자사 발주 내역을 확인하고, 공급 완료 처리를 하며, 공급 이력을 조회할 수 있습니다.

실행 방법:
    프로젝트 최상위 폴더에서 실행
    python3 interfaces/supplier_cli.py

주요 기능:
    1. 공급업체 로그인
    2. 내 업체 정보 조회
    3. 미처리 발주 목록 조회
    4. 발주 상세 조회
    5. 공급 완료 처리
    6. 공급 이력 조회
    7. 재고 반영 확인
    0. 종료

공급 완료 처리 시 수행 작업:
    - 공급내역 INSERT
    - 발주 상태를 '완료'로 변경
    - 보유 테이블의 재고수량 증가
    - 하나의 트랜잭션으로 처리하여 중간 실패 시 ROLLBACK
"""

import random
import sqlite3
from datetime import datetime
from pathlib import Path


DEFAULT_DB_NAMES = ["파리바게트.db", "paris_baguette.db", "database.db"]


class SupplierCLI:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.conn = None
        self.supplier_code = None
        self.supplier_name = None

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
        required = {"공급업체", "발주", "발주상세", "공급내역", "보유", "상품", "브랜드", "지점"}
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
            print("주의: 공급업체 CLI 실행에 필요한 일부 테이블이 없습니다.")
            print("누락 테이블:", ", ".join(missing))

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

    def run(self):
        self.connect()

        if not self.login():
            self.close()
            return

        while True:
            print_menu(self.supplier_name, self.supplier_code)
            choice = input("메뉴 선택 > ").strip()

            try:
                if choice == "1":
                    self.show_my_info()
                elif choice == "2":
                    self.show_pending_orders()
                elif choice == "3":
                    self.show_order_detail()
                elif choice == "4":
                    self.complete_supply()
                elif choice == "5":
                    self.show_supply_history()
                elif choice == "6":
                    self.check_inventory_by_order()
                elif choice == "0":
                    break
                else:
                    print("잘못된 메뉴 번호입니다.")
            except sqlite3.Error as e:
                print(f"SQLite 오류: {e}")
            except Exception as e:
                print(f"오류: {e}")

        self.close()

    def login(self):
        print("\n" + "=" * 60)
        print("공급업체 공급 처리 CLI 로그인")
        print("=" * 60)

        self.print_supplier_list()

        for _ in range(3):
            supplier_code = input("\n업체코드 입력, 종료는 0 > ").strip()

            if supplier_code == "0":
                print("로그인을 취소했습니다.")
                return False

            row = self.fetch_one(
                """
                SELECT 업체코드, 업체명
                FROM 공급업체
                WHERE 업체코드 = ?;
                """,
                (supplier_code,),
            )

            if row:
                self.supplier_code = row["업체코드"]
                self.supplier_name = row["업체명"]
                print(f"\n로그인 성공: {self.supplier_name} ({self.supplier_code})")
                return True

            print("등록되지 않은 업체코드입니다.")

        print("로그인 실패 횟수가 초과되어 프로그램을 종료합니다.")
        return False

    def print_supplier_list(self):
        rows = self.fetch_all(
            """
            SELECT 업체코드, 업체명, 담당자명, 연락처
            FROM 공급업체
            ORDER BY 업체코드;
            """
        )

        if not rows:
            print("등록된 공급업체가 없습니다.")
            return

        print("\n[등록 공급업체 참고]")
        print_rows(rows)

    def show_my_info(self):
        print("\n[1] 내 업체 정보 조회")

        row = self.fetch_one(
            """
            SELECT 업체코드, 업체명, 담당자명, 연락처
            FROM 공급업체
            WHERE 업체코드 = ?;
            """,
            (self.supplier_code,),
        )

        print_rows([row] if row else [])

        brand_rows = self.fetch_all(
            """
            SELECT b.브랜드코드, b.브랜드명, b.제조사정보
            FROM 취급 c
            JOIN 브랜드 b ON c.브랜드코드 = b.브랜드코드
            WHERE c.업체코드 = ?
            ORDER BY b.브랜드명;
            """,
            (self.supplier_code,),
        )

        print("\n[취급 브랜드]")
        print_rows(brand_rows)

        product_rows = self.fetch_all(
            """
            SELECT p.상품코드, p.이름 AS 상품명, b.브랜드명, p.가격
            FROM 공급 s
            JOIN 상품 p ON s.상품코드 = p.상품코드
            LEFT JOIN 브랜드 b ON p.브랜드코드 = b.브랜드코드
            WHERE s.업체코드 = ?
            ORDER BY b.브랜드명, p.이름
            LIMIT 30;
            """,
            (self.supplier_code,),
        )

        print("\n[공급 가능 상품 일부]")
        print_rows(product_rows)

    def show_pending_orders(self):
        print("\n[2] 미처리 발주 목록 조회")

        rows = self.fetch_all(
            """
            SELECT
                o.발주번호,
                o.발주일자,
                o.상태,
                o.지점명,
                j.지역_시도,
                COUNT(od.항목번호) AS 발주항목수,
                SUM(od.주문수량) AS 총주문수량
            FROM 발주 o
            JOIN 지점 j ON o.지점명 = j.지점명
            LEFT JOIN 발주상세 od ON o.발주번호 = od.발주번호
            WHERE o.업체코드 = ?
              AND o.상태 <> '완료'
            GROUP BY o.발주번호, o.발주일자, o.상태, o.지점명, j.지역_시도
            ORDER BY o.발주일자, o.발주번호;
            """,
            (self.supplier_code,),
        )

        if not rows:
            print("미처리 발주가 없습니다.")
            return

        print_rows(rows)

    def show_order_detail(self):
        print("\n[3] 발주 상세 조회")
        order_no = input("조회할 발주번호 입력 > ").strip()

        if not order_no:
            print("발주번호를 입력해야 합니다.")
            return

        if not self.check_order_access(order_no):
            print("해당 발주번호가 없거나 현재 로그인한 공급업체의 발주가 아닙니다.")
            return

        self.print_order_header(order_no)
        self.print_order_items(order_no)

    def complete_supply(self):
        print("\n[4] 공급 완료 처리")
        self.show_pending_orders()

        order_no = input("\n공급 완료 처리할 발주번호 입력, 취소는 Enter > ").strip()

        if not order_no:
            print("공급 완료 처리를 취소했습니다.")
            return

        order = self.fetch_one(
            """
            SELECT 발주번호, 발주일자, 상태, 지점명, 업체코드
            FROM 발주
            WHERE 발주번호 = ?
              AND 업체코드 = ?;
            """,
            (order_no, self.supplier_code),
        )

        if not order:
            print("해당 발주번호가 없거나 현재 로그인한 공급업체의 발주가 아닙니다.")
            return

        if order["상태"] == "완료":
            print("이미 완료 처리된 발주입니다.")
            return

        items = self.fetch_all(
            """
            SELECT
                od.발주번호,
                od.항목번호,
                od.상품코드,
                p.이름 AS 상품명,
                od.주문수량,
                h.재고수량 AS 현재재고수량,
                h.최소재고기준
            FROM 발주상세 od
            JOIN 상품 p ON od.상품코드 = p.상품코드
            LEFT JOIN 보유 h ON h.지점명 = ? AND h.상품코드 = od.상품코드
            WHERE od.발주번호 = ?
            ORDER BY od.항목번호;
            """,
            (order["지점명"], order_no),
        )

        if not items:
            print("발주상세 항목이 없어 공급 완료 처리를 할 수 없습니다.")
            return

        print("\n[처리 대상 발주]")
        self.print_order_header(order_no)
        print("\n[공급 처리 항목]")
        print_rows(items)

        print("\n공급 완료 처리 시 주문수량만큼 매장 재고가 증가하고, 발주 상태가 '완료'로 변경됩니다.")
        confirm = input("정말 처리할까요? (y/N) > ").strip().lower()

        if confirm != "y":
            print("공급 완료 처리를 취소했습니다.")
            return

        supply_no = self.generate_supply_no()
        total_qty = sum(row["주문수량"] for row in items)
        supplied_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            self.conn.execute("BEGIN IMMEDIATE;")

            self.conn.execute(
                """
                INSERT INTO 공급내역 (공급번호, 공급일시, 공급수량, 발주번호, 업체코드)
                VALUES (?, ?, ?, ?, ?);
                """,
                (supply_no, supplied_at, total_qty, order_no, self.supplier_code),
            )

            for item in items:
                current_inventory = item["현재재고수량"]

                if current_inventory is None:
                    self.conn.execute(
                        """
                        INSERT INTO 보유 (지점명, 상품코드, 재고수량, 최소재고기준, 매장가격)
                        SELECT ?, p.상품코드, ?, 10, p.가격
                        FROM 상품 p
                        WHERE p.상품코드 = ?;
                        """,
                        (order["지점명"], item["주문수량"], item["상품코드"]),
                    )
                else:
                    self.conn.execute(
                        """
                        UPDATE 보유
                        SET 재고수량 = 재고수량 + ?
                        WHERE 지점명 = ?
                          AND 상품코드 = ?;
                        """,
                        (item["주문수량"], order["지점명"], item["상품코드"]),
                    )

            self.conn.execute(
                """
                UPDATE 발주
                SET 상태 = '완료'
                WHERE 발주번호 = ?
                  AND 업체코드 = ?;
                """,
                (order_no, self.supplier_code),
            )

            self.conn.commit()

        except Exception:
            self.conn.rollback()
            raise

        print("\n공급 완료 처리가 정상적으로 완료되었습니다.")
        print(f"공급번호: {supply_no}")
        print(f"공급일시: {supplied_at}")
        print(f"총 공급수량: {total_qty}")
        print("발주 상태: 완료")
        print("재고 반영: 완료")

    def show_supply_history(self):
        print("\n[5] 공급 이력 조회")
        start_date = input("시작일 YYYY-MM-DD, 전체는 Enter > ").strip()
        end_date = input("종료일 YYYY-MM-DD, 전체는 Enter > ").strip()
        store_keyword = input("지점명 검색어, 전체는 Enter > ").strip()

        conditions = ["s.업체코드 = ?"]
        params = [self.supplier_code]

        if start_date:
            conditions.append("date(s.공급일시) >= ?")
            params.append(start_date)

        if end_date:
            conditions.append("date(s.공급일시) <= ?")
            params.append(end_date)

        if store_keyword:
            conditions.append("o.지점명 LIKE ?")
            params.append(f"%{store_keyword}%")

        where_sql = "WHERE " + " AND ".join(conditions)

        rows = self.fetch_all(
            f"""
            SELECT
                s.공급번호,
                s.공급일시,
                s.공급수량,
                s.발주번호,
                o.발주일자,
                o.상태 AS 발주상태,
                o.지점명
            FROM 공급내역 s
            JOIN 발주 o ON s.발주번호 = o.발주번호
            {where_sql}
            ORDER BY s.공급일시 DESC, s.공급번호 DESC;
            """,
            params,
        )

        print_rows(rows)

    def check_inventory_by_order(self):
        print("\n[6] 재고 반영 확인")
        order_no = input("확인할 발주번호 입력 > ").strip()

        if not order_no:
            print("발주번호를 입력해야 합니다.")
            return

        if not self.check_order_access(order_no):
            print("해당 발주번호가 없거나 현재 로그인한 공급업체의 발주가 아닙니다.")
            return

        order = self.fetch_one(
            """
            SELECT 발주번호, 지점명, 상태
            FROM 발주
            WHERE 발주번호 = ?
              AND 업체코드 = ?;
            """,
            (order_no, self.supplier_code),
        )

        rows = self.fetch_all(
            """
            SELECT
                od.발주번호,
                o.지점명,
                od.상품코드,
                p.이름 AS 상품명,
                od.주문수량,
                h.재고수량 AS 현재재고수량,
                h.최소재고기준,
                CASE
                    WHEN h.재고수량 IS NULL THEN '보유정보 없음'
                    WHEN h.재고수량 < h.최소재고기준 THEN '재고부족'
                    ELSE '정상'
                END AS 재고상태
            FROM 발주상세 od
            JOIN 발주 o ON od.발주번호 = o.발주번호
            JOIN 상품 p ON od.상품코드 = p.상품코드
            LEFT JOIN 보유 h ON h.지점명 = o.지점명 AND h.상품코드 = od.상품코드
            WHERE od.발주번호 = ?
            ORDER BY od.항목번호;
            """,
            (order_no,),
        )

        print(f"\n발주번호: {order_no}")
        print(f"지점명: {order['지점명']}")
        print(f"발주상태: {order['상태']}")
        print_rows(rows)

    def print_order_header(self, order_no):
        rows = self.fetch_all(
            """
            SELECT
                o.발주번호,
                o.발주일자,
                o.상태,
                o.지점명,
                j.지역_시도,
                j.주소,
                s.업체명
            FROM 발주 o
            JOIN 지점 j ON o.지점명 = j.지점명
            JOIN 공급업체 s ON o.업체코드 = s.업체코드
            WHERE o.발주번호 = ?
              AND o.업체코드 = ?;
            """,
            (order_no, self.supplier_code),
        )
        print_rows(rows)

    def print_order_items(self, order_no):
        rows = self.fetch_all(
            """
            SELECT
                od.항목번호,
                od.상품코드,
                p.이름 AS 상품명,
                b.브랜드명,
                od.주문수량,
                h.재고수량 AS 현재재고수량,
                h.최소재고기준
            FROM 발주상세 od
            JOIN 상품 p ON od.상품코드 = p.상품코드
            LEFT JOIN 브랜드 b ON p.브랜드코드 = b.브랜드코드
            JOIN 발주 o ON od.발주번호 = o.발주번호
            LEFT JOIN 보유 h ON h.지점명 = o.지점명 AND h.상품코드 = od.상품코드
            WHERE od.발주번호 = ?
            ORDER BY od.항목번호;
            """,
            (order_no,),
        )
        print("\n[발주상세]")
        print_rows(rows)

    def check_order_access(self, order_no):
        row = self.fetch_one(
            """
            SELECT 발주번호
            FROM 발주
            WHERE 발주번호 = ?
              AND 업체코드 = ?;
            """,
            (order_no, self.supplier_code),
        )
        return row is not None

    def generate_supply_no(self):
        while True:
            supply_no = "SI" + datetime.now().strftime("%y%m%d%H%M%S") + str(random.randint(10, 99))
            exists = self.fetch_one(
                """
                SELECT 공급번호
                FROM 공급내역
                WHERE 공급번호 = ?;
                """,
                (supply_no,),
            )
            if not exists:
                return supply_no


def print_menu(supplier_name, supplier_code):
    print("\n" + "=" * 70)
    print(f"공급업체 공급 처리 CLI - {supplier_name} ({supplier_code})")
    print("=" * 70)
    print("1. 내 업체 정보 조회")
    print("2. 미처리 발주 목록 조회")
    print("3. 발주 상세 조회")
    print("4. 공급 완료 처리")
    print("5. 공급 이력 조회")
    print("6. 재고 반영 확인")
    print("0. 종료")
    print("=" * 70)


def print_rows(rows, max_width=24):
    if not rows:
        print("조회 결과가 없습니다.")
        return

    headers = list(rows[0].keys())
    str_rows = []

    for row in rows:
        str_rows.append([format_cell(row[h], max_width) for h in headers])

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


def main():
    print("공급업체 공급 처리 CLI 실행")
    db_path = select_db_path()

    if not db_path:
        print("DB 파일 경로가 입력되지 않아 종료합니다.")
        return

    cli = SupplierCLI(db_path)
    cli.run()


if __name__ == "__main__":
    main()
