"""
OLAP 분석 대시보드
Team 발닦고디비자라 - 파리바게트 지점 재고 및 판매 관리 시스템

이 파일은 사용자 인터페이스 기능 설명서의 "OLAP 분석 대시보드"를 구현한 CLI 프로그램입니다.
본사 운영팀이 판매/재고 데이터를 읽기 전용으로 분석하는 용도입니다.

실행 방법:
    프로젝트 최상위 폴더에서 실행
    python3 interfaces/olap_dashboard.py

DB 파일 위치:
    다음 위치에서 자동 탐색합니다.
    - ./파리바게트.db
    - ./paris_baguette.db
    - ./database.db
    - ./data/파리바게트.db
    - ./data/paris_baguette.db
    - ./data/database.db

주요 기능:
    1. 매장별 베스트셀러 TOP N
    2. 지역별 베스트셀러 TOP N
    3. 판매 실적 상위 매장 TOP N
    4. 브랜드별 매출 비교
    5. 연관 상품 분석
    6. 카테고리별 매출 비중
    7. 재고 회전율 분석
    8. 월별 매출 추이
    9. 기본 데이터 현황 조회
    10. 최근 분석 결과 CSV 저장

주의:
    이 인터페이스는 OLAP용 읽기 전용 분석 대시보드입니다.
    판매/재고/발주 데이터를 직접 수정하지 않습니다.
"""

import csv
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple


DEFAULT_DB_NAMES = ["파리바게트.db", "paris_baguette.db", "database.db"]
RESULT_DIR = "results"


class OLAPDashboard:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.conn: Optional[sqlite3.Connection] = None
        self.last_rows: List[sqlite3.Row] = []
        self.last_title: str = "olap_result"

    def connect(self) -> None:
        if not self.db_path.exists():
            raise FileNotFoundError(f"DB 파일을 찾을 수 없습니다: {self.db_path}")

        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.validate_required_tables()
        print(f"\nDB 접속 완료: {self.db_path}")

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            print("DB 연결을 종료했습니다.")

    def validate_required_tables(self) -> None:
        required = {"판매", "판매상세", "상품", "브랜드", "지점", "보유"}
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
            print("주의: OLAP 분석에 필요한 일부 테이블이 없습니다.")
            print("누락 테이블:", ", ".join(missing))

    def run(self) -> None:
        self.connect()

        while True:
            print_menu()
            choice = input("메뉴 선택 > ").strip()

            try:
                if choice == "1":
                    self.top_sellers_by_store()
                elif choice == "2":
                    self.top_sellers_by_region()
                elif choice == "3":
                    self.top_stores_by_sales()
                elif choice == "4":
                    self.compare_brands()
                elif choice == "5":
                    self.association_analysis()
                elif choice == "6":
                    self.category_sales_share()
                elif choice == "7":
                    self.inventory_turnover()
                elif choice == "8":
                    self.monthly_sales_trend()
                elif choice == "9":
                    self.basic_data_summary()
                elif choice == "10":
                    self.export_last_result_to_csv()
                elif choice == "0":
                    break
                else:
                    print("잘못된 메뉴 번호입니다.")
            except sqlite3.Error as e:
                print(f"SQLite 오류: {e}")
            except Exception as e:
                print(f"오류: {e}")

        self.close()

    def fetch_all(self, sql: str, params: Sequence = ()) -> List[sqlite3.Row]:
        if self.conn is None:
            raise RuntimeError("DB 연결이 없습니다.")
        cur = self.conn.execute(sql, params)
        return cur.fetchall()

    def save_last_result(self, title: str, rows: List[sqlite3.Row]) -> None:
        self.last_title = title
        self.last_rows = rows

    def ask_save_csv(self) -> None:
        if not self.last_rows:
            return
        answer = input("\n이 결과를 CSV로 저장할까요? (y/N) > ").strip().lower()
        if answer == "y":
            self.export_last_result_to_csv()

    def export_last_result_to_csv(self) -> None:
        if not self.last_rows:
            print("저장할 최근 분석 결과가 없습니다.")
            return

        result_dir = Path(RESULT_DIR)
        result_dir.mkdir(exist_ok=True)

        safe_title = sanitize_filename(self.last_title)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = result_dir / f"{safe_title}_{timestamp}.csv"

        with open(filename, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(self.last_rows[0].keys())
            for row in self.last_rows:
                writer.writerow([row[key] for key in row.keys()])

        print(f"CSV 저장 완료: {filename}")

    def top_sellers_by_store(self) -> None:
        print("\n[1] 매장별 베스트셀러 TOP N")
        self.print_available_stores()
        store_name = input("매장명 검색어 입력, 전체 매장은 Enter > ").strip()
        n = input_int("매장별 TOP N", default=20, min_value=1)
        start_date, end_date = input_period()

        conditions = []
        params: List = []

        if store_name:
            conditions.append("v.지점명 LIKE ?")
            params.append(f"%{store_name}%")

        add_period_conditions(conditions, params, "v.판매일자", start_date, end_date)
        where_sql = make_where_sql(conditions)

        params.append(n)

        sql = f"""
        WITH base AS (
            SELECT
                v.지점명 AS 지점명,
                p.상품코드 AS 상품코드,
                p.이름 AS 상품명,
                b.브랜드명 AS 브랜드명,
                SUM(vd.수량) AS 판매수량,
                SUM(vd.수량 * vd.판매단가) AS 매출액,
                COUNT(DISTINCT v.판매번호) AS 판매건수
            FROM 판매 v
            JOIN 판매상세 vd ON v.판매번호 = vd.판매번호
            JOIN 상품 p ON vd.상품코드 = p.상품코드
            LEFT JOIN 브랜드 b ON p.브랜드코드 = b.브랜드코드
            {where_sql}
            GROUP BY v.지점명, p.상품코드, p.이름, b.브랜드명
        ),
        ranked AS (
            SELECT
                지점명,
                상품코드,
                상품명,
                브랜드명,
                판매수량,
                매출액,
                판매건수,
                ROW_NUMBER() OVER (
                    PARTITION BY 지점명
                    ORDER BY 판매수량 DESC, 매출액 DESC
                ) AS 순위
            FROM base
        )
        SELECT
            지점명,
            순위,
            상품코드,
            상품명,
            브랜드명,
            판매수량,
            매출액,
            판매건수
        FROM ranked
        WHERE 순위 <= ?
        ORDER BY 지점명, 순위;
        """

        rows = self.fetch_all(sql, params)
        print_rows(rows)
        self.save_last_result("매장별_베스트셀러", rows)
        self.ask_save_csv()

    def top_sellers_by_region(self) -> None:
        print("\n[2] 지역별 베스트셀러 TOP N")
        self.print_available_regions()
        region = input("지역/시도 검색어 입력, 전체 지역은 Enter > ").strip()
        n = input_int("지역별 TOP N", default=20, min_value=1)
        start_date, end_date = input_period()

        conditions = []
        params: List = []

        if region:
            conditions.append("j.지역_시도 LIKE ?")
            params.append(f"%{region}%")

        add_period_conditions(conditions, params, "v.판매일자", start_date, end_date)
        where_sql = make_where_sql(conditions)

        params.append(n)

        sql = f"""
        WITH base AS (
            SELECT
                j.지역_시도 AS 지역_시도,
                p.상품코드 AS 상품코드,
                p.이름 AS 상품명,
                b.브랜드명 AS 브랜드명,
                SUM(vd.수량) AS 판매수량,
                SUM(vd.수량 * vd.판매단가) AS 매출액,
                COUNT(DISTINCT v.판매번호) AS 판매건수
            FROM 판매 v
            JOIN 지점 j ON v.지점명 = j.지점명
            JOIN 판매상세 vd ON v.판매번호 = vd.판매번호
            JOIN 상품 p ON vd.상품코드 = p.상품코드
            LEFT JOIN 브랜드 b ON p.브랜드코드 = b.브랜드코드
            {where_sql}
            GROUP BY j.지역_시도, p.상품코드, p.이름, b.브랜드명
        ),
        ranked AS (
            SELECT
                지역_시도,
                상품코드,
                상품명,
                브랜드명,
                판매수량,
                매출액,
                판매건수,
                ROW_NUMBER() OVER (
                    PARTITION BY 지역_시도
                    ORDER BY 판매수량 DESC, 매출액 DESC
                ) AS 순위
            FROM base
        )
        SELECT
            지역_시도,
            순위,
            상품코드,
            상품명,
            브랜드명,
            판매수량,
            매출액,
            판매건수
        FROM ranked
        WHERE 순위 <= ?
        ORDER BY 지역_시도, 순위;
        """

        rows = self.fetch_all(sql, params)
        print_rows(rows)
        self.save_last_result("지역별_베스트셀러", rows)
        self.ask_save_csv()

    def top_stores_by_sales(self) -> None:
        print("\n[3] 판매 실적 상위 매장 TOP N")
        n = input_int("상위 매장 수", default=5, min_value=1)
        start_date, end_date = input_period()

        conditions = []
        params: List = []
        add_period_conditions(conditions, params, "판매일자", start_date, end_date)
        where_sql = make_where_sql(conditions)

        params.append(n)

        sql = f"""
        WITH sale_base AS (
            SELECT
                판매번호,
                판매일자,
                지점명,
                총판매금액
            FROM 판매
            {where_sql}
        ),
        item_qty AS (
            SELECT
                판매번호,
                SUM(수량) AS 총판매수량
            FROM 판매상세
            GROUP BY 판매번호
        )
        SELECT
            sb.지점명 AS 지점명,
            j.지역_시도 AS 지역_시도,
            COUNT(sb.판매번호) AS 판매건수,
            SUM(COALESCE(iq.총판매수량, 0)) AS 총판매수량,
            SUM(sb.총판매금액) AS 총매출액,
            ROUND(AVG(sb.총판매금액), 1) AS 건당평균금액
        FROM sale_base sb
        JOIN 지점 j ON sb.지점명 = j.지점명
        LEFT JOIN item_qty iq ON sb.판매번호 = iq.판매번호
        GROUP BY sb.지점명, j.지역_시도
        ORDER BY 총매출액 DESC, 판매건수 DESC
        LIMIT ?;
        """

        rows = self.fetch_all(sql, params)
        print_rows(rows)
        self.save_last_result("판매실적_상위매장", rows)
        self.ask_save_csv()

    def compare_brands(self) -> None:
        print("\n[4] 브랜드별 매출 비교")
        self.print_available_brands()

        brand_a = input("비교할 브랜드 A 입력 > ").strip()
        brand_b = input("비교할 브랜드 B 입력 > ").strip()

        if not brand_a or not brand_b:
            print("브랜드 A와 브랜드 B를 모두 입력해야 합니다.")
            return

        start_date, end_date = input_period()

        conditions = []
        params: List = []
        add_period_conditions(conditions, params, "v.판매일자", start_date, end_date)
        where_sql = make_where_sql(conditions)

        brand_a_like = f"%{brand_a}%"
        brand_b_like = f"%{brand_b}%"

        sql = f"""
        WITH brand_sales AS (
            SELECT
                v.지점명 AS 지점명,
                j.지역_시도 AS 지역_시도,
                SUM(CASE WHEN b.브랜드명 LIKE ? THEN vd.수량 * vd.판매단가 ELSE 0 END) AS 브랜드A_매출액,
                SUM(CASE WHEN b.브랜드명 LIKE ? THEN vd.수량 * vd.판매단가 ELSE 0 END) AS 브랜드B_매출액,
                SUM(CASE WHEN b.브랜드명 LIKE ? THEN vd.수량 ELSE 0 END) AS 브랜드A_판매수량,
                SUM(CASE WHEN b.브랜드명 LIKE ? THEN vd.수량 ELSE 0 END) AS 브랜드B_판매수량
            FROM 판매 v
            JOIN 지점 j ON v.지점명 = j.지점명
            JOIN 판매상세 vd ON v.판매번호 = vd.판매번호
            JOIN 상품 p ON vd.상품코드 = p.상품코드
            JOIN 브랜드 b ON p.브랜드코드 = b.브랜드코드
            {where_sql}
            GROUP BY v.지점명, j.지역_시도
        )
        SELECT
            지점명,
            지역_시도,
            브랜드A_매출액 AS "{brand_a}_매출액",
            브랜드B_매출액 AS "{brand_b}_매출액",
            브랜드A_판매수량 AS "{brand_a}_판매수량",
            브랜드B_판매수량 AS "{brand_b}_판매수량",
            CASE
                WHEN 브랜드A_매출액 > 브랜드B_매출액 THEN ?
                WHEN 브랜드A_매출액 < 브랜드B_매출액 THEN ?
                ELSE '동일'
            END AS 우세브랜드
        FROM brand_sales
        WHERE 브랜드A_매출액 > 0 OR 브랜드B_매출액 > 0
        ORDER BY 지점명;
        """

        query_params = [
            brand_a_like,
            brand_b_like,
            brand_a_like,
            brand_b_like,
            *params,
            brand_a,
            brand_b,
        ]

        rows = self.fetch_all(sql, query_params)
        print_rows(rows)

        a_win = sum(1 for row in rows if row["우세브랜드"] == brand_a)
        b_win = sum(1 for row in rows if row["우세브랜드"] == brand_b)
        tie = sum(1 for row in rows if row["우세브랜드"] == "동일")

        print("\n[브랜드 비교 요약]")
        print(f"{brand_a} 우세 매장 수: {a_win}")
        print(f"{brand_b} 우세 매장 수: {b_win}")
        print(f"동일 매장 수: {tie}")
        print(f"분석 대상 매장 수: {len(rows)}")

        self.save_last_result("브랜드별_매출비교", rows)
        self.ask_save_csv()

    def association_analysis(self) -> None:
        print("\n[5] 연관 상품 분석")
        print("예: 우유와 함께 가장 많이 구매된 상품 TOP 3")
        keyword = input("기준 상품명 또는 상품코드 입력, Enter=우유 > ").strip() or "우유"
        n = input_int("연관 상품 TOP N", default=3, min_value=1)
        start_date, end_date = input_period()

        conditions = []
        params: List = []
        add_period_conditions(conditions, params, "v.판매일자", start_date, end_date)
        where_sql = make_where_sql(conditions)

        sql = f"""
        WITH target_product AS (
            SELECT 상품코드, 이름
            FROM 상품
            WHERE 상품코드 = ?
               OR 이름 LIKE ?
        ),
        target_sales AS (
            SELECT DISTINCT
                v.판매번호,
                tp.상품코드 AS 기준상품코드,
                tp.이름 AS 기준상품명
            FROM 판매 v
            JOIN 판매상세 vd ON v.판매번호 = vd.판매번호
            JOIN target_product tp ON vd.상품코드 = tp.상품코드
            {where_sql}
        ),
        related AS (
            SELECT
                ts.기준상품명 AS 기준상품명,
                p.상품코드 AS 연관상품코드,
                p.이름 AS 연관상품명,
                b.브랜드명 AS 브랜드명,
                COUNT(DISTINCT vd.판매번호) AS 함께구매된판매건수,
                SUM(vd.수량) AS 함께구매된수량,
                SUM(vd.수량 * vd.판매단가) AS 연관상품매출액
            FROM target_sales ts
            JOIN 판매상세 vd ON ts.판매번호 = vd.판매번호
            JOIN 상품 p ON vd.상품코드 = p.상품코드
            LEFT JOIN 브랜드 b ON p.브랜드코드 = b.브랜드코드
            WHERE vd.상품코드 <> ts.기준상품코드
            GROUP BY ts.기준상품명, p.상품코드, p.이름, b.브랜드명
        )
        SELECT
            기준상품명,
            연관상품코드,
            연관상품명,
            브랜드명,
            함께구매된판매건수,
            함께구매된수량,
            연관상품매출액
        FROM related
        ORDER BY 함께구매된판매건수 DESC, 함께구매된수량 DESC, 연관상품매출액 DESC
        LIMIT ?;
        """

        query_params = [keyword, f"%{keyword}%", *params, n]
        rows = self.fetch_all(sql, query_params)
        print_rows(rows)

        if not rows:
            print("기준 상품을 찾지 못했거나, 함께 구매된 상품 데이터가 없습니다.")

        self.save_last_result("연관상품_분석", rows)
        self.ask_save_csv()

    def category_sales_share(self) -> None:
        print("\n[6] 카테고리별 매출 비중")
        start_date, end_date = input_period()

        conditions = []
        params: List = []
        add_period_conditions(conditions, params, "v.판매일자", start_date, end_date)
        where_sql = make_where_sql(conditions)

        sql = f"""
        WITH product_category AS (
            SELECT
                p.상품코드,
                p.이름,
                CASE
                    WHEN EXISTS (SELECT 1 FROM 빵 x WHERE x.상품코드 = p.상품코드) THEN '빵'
                    WHEN EXISTS (SELECT 1 FROM 케이크 x WHERE x.상품코드 = p.상품코드) THEN '케이크'
                    WHEN EXISTS (SELECT 1 FROM 샐러드 x WHERE x.상품코드 = p.상품코드) THEN '샐러드'
                    WHEN EXISTS (SELECT 1 FROM 음료 x WHERE x.상품코드 = p.상품코드) THEN '음료'
                    WHEN EXISTS (SELECT 1 FROM 스낵 x WHERE x.상품코드 = p.상품코드) THEN '스낵'
                    ELSE '기타'
                END AS 카테고리
            FROM 상품 p
        ),
        category_sales AS (
            SELECT
                pc.카테고리 AS 카테고리,
                SUM(vd.수량) AS 판매수량,
                SUM(vd.수량 * vd.판매단가) AS 매출액,
                COUNT(DISTINCT v.판매번호) AS 판매건수
            FROM 판매 v
            JOIN 판매상세 vd ON v.판매번호 = vd.판매번호
            JOIN product_category pc ON vd.상품코드 = pc.상품코드
            {where_sql}
            GROUP BY pc.카테고리
        )
        SELECT
            카테고리,
            판매수량,
            매출액,
            판매건수,
            ROUND(매출액 * 100.0 / SUM(매출액) OVER (), 2) AS 매출비중_퍼센트
        FROM category_sales
        ORDER BY 매출액 DESC;
        """

        rows = self.fetch_all(sql, params)
        print_rows(rows)
        self.save_last_result("카테고리별_매출비중", rows)
        self.ask_save_csv()

    def inventory_turnover(self) -> None:
        print("\n[7] 재고 회전율 분석")
        print("현재 재고 대비 기간 판매수량을 비교합니다.")
        self.print_available_stores()
        store_name = input("매장명 검색어 입력, 전체 매장은 Enter > ").strip()
        n = input_int("상위 N개 상품", default=30, min_value=1)
        start_date, end_date = input_period()

        sale_conditions = []
        params: List = []
        add_period_conditions(sale_conditions, params, "v.판매일자", start_date, end_date)
        sale_where_sql = make_where_sql(sale_conditions)

        outer_conditions = []
        outer_params: List = []
        if store_name:
            outer_conditions.append("h.지점명 LIKE ?")
            outer_params.append(f"%{store_name}%")
        outer_where_sql = make_where_sql(outer_conditions)

        sql = f"""
        WITH sales_qty AS (
            SELECT
                v.지점명 AS 지점명,
                vd.상품코드 AS 상품코드,
                SUM(vd.수량) AS 기간판매수량,
                SUM(vd.수량 * vd.판매단가) AS 기간매출액
            FROM 판매 v
            JOIN 판매상세 vd ON v.판매번호 = vd.판매번호
            {sale_where_sql}
            GROUP BY v.지점명, vd.상품코드
        )
        SELECT
            h.지점명 AS 지점명,
            j.지역_시도 AS 지역_시도,
            p.상품코드 AS 상품코드,
            p.이름 AS 상품명,
            b.브랜드명 AS 브랜드명,
            h.재고수량 AS 현재재고수량,
            h.최소재고기준 AS 최소재고기준,
            COALESCE(sq.기간판매수량, 0) AS 기간판매수량,
            COALESCE(sq.기간매출액, 0) AS 기간매출액,
            CASE
                WHEN h.재고수량 = 0 AND COALESCE(sq.기간판매수량, 0) > 0 THEN '재고소진'
                WHEN h.재고수량 < h.최소재고기준 THEN '재고부족'
                ELSE '정상'
            END AS 재고상태,
            CASE
                WHEN h.재고수량 = 0 THEN NULL
                ELSE ROUND(COALESCE(sq.기간판매수량, 0) * 1.0 / h.재고수량, 2)
            END AS 판매재고비율
        FROM 보유 h
        JOIN 지점 j ON h.지점명 = j.지점명
        JOIN 상품 p ON h.상품코드 = p.상품코드
        LEFT JOIN 브랜드 b ON p.브랜드코드 = b.브랜드코드
        LEFT JOIN sales_qty sq ON h.지점명 = sq.지점명 AND h.상품코드 = sq.상품코드
        {outer_where_sql}
        ORDER BY
            CASE WHEN h.재고수량 = 0 AND COALESCE(sq.기간판매수량, 0) > 0 THEN 999999
                 WHEN h.재고수량 = 0 THEN 0
                 ELSE COALESCE(sq.기간판매수량, 0) * 1.0 / h.재고수량
            END DESC,
            기간매출액 DESC
        LIMIT ?;
        """

        query_params = [*params, *outer_params, n]
        rows = self.fetch_all(sql, query_params)
        print_rows(rows)
        self.save_last_result("재고회전율_분석", rows)
        self.ask_save_csv()

    def monthly_sales_trend(self) -> None:
        print("\n[8] 월별 매출 추이")
        self.print_available_stores()
        store_name = input("매장명 검색어 입력, 전체 매장은 Enter > ").strip()
        start_date, end_date = input_period()

        conditions = []
        params: List = []

        if store_name:
            conditions.append("v.지점명 LIKE ?")
            params.append(f"%{store_name}%")

        add_period_conditions(conditions, params, "v.판매일자", start_date, end_date)
        where_sql = make_where_sql(conditions)

        sql = f"""
        WITH item_qty AS (
            SELECT
                판매번호,
                SUM(수량) AS 판매수량
            FROM 판매상세
            GROUP BY 판매번호
        )
        SELECT
            strftime('%Y-%m', v.판매일자) AS 판매월,
            COUNT(v.판매번호) AS 판매건수,
            SUM(COALESCE(iq.판매수량, 0)) AS 판매수량,
            SUM(v.총판매금액) AS 매출액,
            ROUND(AVG(v.총판매금액), 1) AS 건당평균금액
        FROM 판매 v
        LEFT JOIN item_qty iq ON v.판매번호 = iq.판매번호
        {where_sql}
        GROUP BY strftime('%Y-%m', v.판매일자)
        ORDER BY 판매월;
        """

        rows = self.fetch_all(sql, params)
        print_rows(rows)
        self.save_last_result("월별_매출추이", rows)
        self.ask_save_csv()

    def basic_data_summary(self) -> None:
        print("\n[9] 기본 데이터 현황 조회")

        target_tables = [
            "브랜드", "공급업체", "지점", "상품", "직원", "고객",
            "회원", "비회원", "판매", "판매상세", "보유", "발주", "발주상세", "공급내역"
        ]

        rows_as_dict = []
        for table in target_tables:
            if self.table_exists(table):
                count = self.fetch_all(f'SELECT COUNT(*) AS cnt FROM "{table}";')[0]["cnt"]
                rows_as_dict.append({"테이블명": table, "데이터건수": count})
            else:
                rows_as_dict.append({"테이블명": table, "데이터건수": "테이블 없음"})

        print_dict_rows(rows_as_dict)
        self.last_title = "기본데이터_현황"
        self.last_rows = dicts_to_rows_like(rows_as_dict)
        self.ask_save_csv()

    def table_exists(self, table_name: str) -> bool:
        rows = self.fetch_all(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = ?;
            """,
            (table_name,),
        )
        return bool(rows)

    def print_available_stores(self) -> None:
        rows = self.fetch_all(
            """
            SELECT 지점명, 지역_시도
            FROM 지점
            ORDER BY 지역_시도, 지점명
            LIMIT 20;
            """
        )
        if rows:
            print("\n[참고: 등록 지점 일부]")
            for row in rows:
                print(f"- {row['지점명']} ({row['지역_시도']})")

    def print_available_regions(self) -> None:
        rows = self.fetch_all(
            """
            SELECT DISTINCT 지역_시도
            FROM 지점
            WHERE 지역_시도 IS NOT NULL
            ORDER BY 지역_시도;
            """
        )
        if rows:
            print("\n[참고: 등록 지역]")
            print(", ".join(row["지역_시도"] for row in rows))

    def print_available_brands(self) -> None:
        rows = self.fetch_all(
            """
            SELECT 브랜드명
            FROM 브랜드
            ORDER BY 브랜드명;
            """
        )
        if rows:
            print("\n[참고: 등록 브랜드]")
            print(", ".join(row["브랜드명"] for row in rows))


def print_menu() -> None:
    print("\n" + "=" * 70)
    print("OLAP 분석 대시보드 - 파리바게트 지점 재고 및 판매 관리 시스템")
    print("=" * 70)
    print("1. 매장별 베스트셀러 TOP N")
    print("2. 지역별 베스트셀러 TOP N")
    print("3. 판매 실적 상위 매장 TOP N")
    print("4. 브랜드별 매출 비교")
    print("5. 연관 상품 분석")
    print("6. 카테고리별 매출 비중")
    print("7. 재고 회전율 분석")
    print("8. 월별 매출 추이")
    print("9. 기본 데이터 현황 조회")
    print("10. 최근 분석 결과 CSV 저장")
    print("0. 종료")
    print("=" * 70)


def input_int(prompt: str, default: int, min_value: Optional[int] = None) -> int:
    while True:
        raw = input(f"{prompt} 입력, Enter={default} > ").strip()
        if not raw:
            return default

        try:
            value = int(raw)
        except ValueError:
            print("정수를 입력해야 합니다.")
            continue

        if min_value is not None and value < min_value:
            print(f"{min_value} 이상의 값을 입력해야 합니다.")
            continue

        return value


def input_period() -> Tuple[str, str]:
    print("\n분석 기간을 입력하세요. 전체 기간은 Enter를 누르면 됩니다.")
    start_date = input("시작일 YYYY-MM-DD, Enter=전체 > ").strip()
    end_date = input("종료일 YYYY-MM-DD, Enter=전체 > ").strip()

    if start_date and not is_valid_date(start_date):
        print("시작일 형식이 올바르지 않아 전체 시작 기간으로 처리합니다.")
        start_date = ""

    if end_date and not is_valid_date(end_date):
        print("종료일 형식이 올바르지 않아 전체 종료 기간으로 처리합니다.")
        end_date = ""

    return start_date, end_date


def is_valid_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def add_period_conditions(
    conditions: List[str],
    params: List,
    column_name: str,
    start_date: str,
    end_date: str,
) -> None:
    if start_date:
        conditions.append(f"{column_name} >= ?")
        params.append(start_date)
    if end_date:
        conditions.append(f"{column_name} <= ?")
        params.append(end_date)


def make_where_sql(conditions: Iterable[str]) -> str:
    condition_list = list(conditions)
    if not condition_list:
        return ""
    return "WHERE " + " AND ".join(condition_list)


def print_rows(rows: Sequence[sqlite3.Row], max_width: int = 24) -> None:
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


def print_dict_rows(rows: Sequence[dict], max_width: int = 24) -> None:
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


def format_cell(value, max_width: int) -> str:
    if value is None:
        text = "NULL"
    else:
        text = str(value)

    text = text.replace("\n", " ")
    if len(text) > max_width:
        return text[: max_width - 3] + "..."
    return text


def sanitize_filename(value: str) -> str:
    blocked = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', ' ']
    result = value
    for ch in blocked:
        result = result.replace(ch, "_")
    return result


class DictRow:
    """CSV 저장을 위해 sqlite3.Row와 비슷하게 동작하는 간단한 래퍼"""

    def __init__(self, data: dict):
        self.data = data

    def keys(self):
        return self.data.keys()

    def __getitem__(self, key):
        return self.data[key]


def dicts_to_rows_like(rows: Sequence[dict]) -> List[DictRow]:
    return [DictRow(row) for row in rows]


def discover_db_paths() -> List[Path]:
    paths = []
    cwd = Path.cwd()

    try:
        script_dir = Path(__file__).resolve().parent
        project_root = script_dir.parent
    except NameError:
        script_dir = cwd
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


def select_db_path() -> str:
    found = discover_db_paths()

    if found:
        print("자동으로 찾은 DB 파일:")
        for idx, path in enumerate(found, 1):
            print(f"{idx}. {path}")

        while True:
            raw = input(f"사용할 DB 번호 선택, Enter=1 > ").strip()
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


def main() -> None:
    print("OLAP 분석 대시보드 실행")
    db_path = select_db_path()

    if not db_path:
        print("DB 파일 경로가 입력되지 않아 종료합니다.")
        return

    dashboard = OLAPDashboard(db_path)
    dashboard.run()


if __name__ == "__main__":
    main()
