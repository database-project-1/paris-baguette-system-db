"""
DBA 콘솔
Team 발닦고디비자라 - 파리바게트 지점 재고 및 판매 관리 시스템

이 파일은 프로젝트에서 사용하는 SQLite 데이터베이스를 확인하고 관리하기 위해 만든
관리자용 CLI 프로그램입니다. 테이블 목록 조회, 테이블 구조 확인, SQL 직접 실행,
트랜잭션 처리, 외래키 정합성 검사, DB 백업 등 DBA 관점에서 필요한 기능을
터미널에서 실행할 수 있도록 구성했습니다.

주요 기능:
1. 테이블 목록 조회
2. 테이블 구조 확인
3. SQL 직접 실행
4. 트랜잭션 시작
5. COMMIT
6. ROLLBACK
7. 인덱스 목록 확인
8. 외래키 정합성 검사
9. 전체 테이블 행 수 조회
10. SELECT 결과 CSV 저장
11. DB 백업 생성

주의:
이 프로그램은 관리자용 기능이므로 SELECT뿐만 아니라 INSERT, UPDATE, DELETE 같은
데이터 변경 SQL도 실행할 수 있습니다. 실제 데이터를 수정할 때는 실행할 SQL을
확인한 뒤 사용하는 것이 좋습니다.
"""


import csv
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


DEFAULT_DB_CANDIDATES = ["파리바게트.db", "paris_baguette.db", "database.db"]


def quote_identifier(identifier: str) -> str:
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'


def find_default_db():
    for candidate in DEFAULT_DB_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None


class DBAConsole:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.conn = None
        self.in_transaction = False

    def connect(self):
        if not self.db_path.exists():
            raise FileNotFoundError(f"DB 파일을 찾을 수 없습니다: {self.db_path}")
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        print(f"\nDB 접속 완료: {self.db_path}")

    def close(self):
        if self.conn:
            if self.in_transaction:
                print("진행 중인 트랜잭션이 있어 ROLLBACK 처리합니다.")
                self.conn.rollback()
            self.conn.close()
            print("DB 연결을 종료했습니다.")

    def run(self):
        self.connect()
        while True:
            self.print_menu()
            choice = input("메뉴 선택 > ").strip()

            try:
                if choice == "1":
                    self.show_tables()
                elif choice == "2":
                    self.show_schema()
                elif choice == "3":
                    self.execute_sql()
                elif choice == "4":
                    self.begin_transaction()
                elif choice == "5":
                    self.commit_transaction()
                elif choice == "6":
                    self.rollback_transaction()
                elif choice == "7":
                    self.show_indexes()
                elif choice == "8":
                    self.check_foreign_keys()
                elif choice == "9":
                    self.show_row_counts()
                elif choice == "10":
                    self.export_select_to_csv()
                elif choice == "11":
                    self.backup_database()
                elif choice == "0":
                    break
                else:
                    print("잘못된 메뉴 번호입니다.")
            except sqlite3.Error as e:
                print(f"SQLite 오류: {e}")
            except Exception as e:
                print(f"오류: {e}")

        self.close()

    @staticmethod
    def print_menu():
        print("\n" + "=" * 60)
        print("DBA Console - 파리바게트 지점 재고 및 판매 관리 시스템")
        print("=" * 60)
        print("1. 테이블 목록 조회")
        print("2. 테이블 스키마 조회")
        print("3. SQL 직접 실행")
        print("4. 트랜잭션 시작 BEGIN")
        print("5. 트랜잭션 확정 COMMIT")
        print("6. 트랜잭션 취소 ROLLBACK")
        print("7. 인덱스 목록 조회")
        print("8. 외래키 정합성 점검")
        print("9. 전체 테이블 행 수 조회")
        print("10. SELECT 결과 CSV 저장")
        print("11. DB 백업 생성")
        print("0. 종료")
        print("=" * 60)

    def fetch_all(self, sql: str, params=()):
        cur = self.conn.execute(sql, params)
        return cur.fetchall()

    @staticmethod
    def print_rows(rows):
        if not rows:
            print("조회 결과가 없습니다.")
            return

        headers = list(rows[0].keys())
        widths = []
        for h in headers:
            max_width = max(len(str(row[h])) for row in rows)
            widths.append(max(max_width, len(h), 8))

        header_line = " | ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(header_line)
        print("-" * len(header_line))

        for row in rows:
            print(" | ".join(str(row[h]).ljust(widths[i]) for i, h in enumerate(headers)))
        print(f"\n총 {len(rows)}행")

    def show_tables(self):
        sql = """
        SELECT name AS table_name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name;
        """
        rows = self.fetch_all(sql)
        self.print_rows(rows)

    def show_schema(self):
        table_name = input("스키마를 조회할 테이블명 > ").strip()
        if not table_name:
            print("테이블명을 입력해야 합니다.")
            return

        table = quote_identifier(table_name)

        print(f"\n[{table_name}] 컬럼 정보")
        self.print_rows(self.fetch_all(f"PRAGMA table_info({table});"))

        print(f"\n[{table_name}] 외래키 정보")
        self.print_rows(self.fetch_all(f"PRAGMA foreign_key_list({table});"))

    def execute_sql(self):
        print("\n실행할 SQL을 입력하세요.")
        print("여러 줄 입력 가능, 마지막 줄에 ; 만 입력하면 실행됩니다.")
        print("취소하려면 빈 줄에서 Enter를 누르세요.")

        lines = []
        while True:
            line = input("SQL > ")
            if not line.strip() and not lines:
                print("SQL 입력을 취소했습니다.")
                return
            if line.strip() == ";":
                break
            lines.append(line)

        sql = "\n".join(lines).strip()
        if not sql:
            print("실행할 SQL이 없습니다.")
            return

        cur = self.conn.cursor()
        cur.execute(sql)

        if sql.lstrip().lower().startswith(("select", "pragma", "with")):
            self.print_rows(cur.fetchall())
        else:
            if not self.in_transaction:
                self.conn.commit()
            print(f"SQL 실행 완료. 영향받은 행 수: {cur.rowcount}")

    def begin_transaction(self):
        if self.in_transaction:
            print("이미 트랜잭션이 진행 중입니다.")
            return
        self.conn.execute("BEGIN IMMEDIATE;")
        self.in_transaction = True
        print("트랜잭션을 시작했습니다. BEGIN IMMEDIATE")

    def commit_transaction(self):
        if not self.in_transaction:
            print("진행 중인 트랜잭션이 없습니다.")
            return
        self.conn.commit()
        self.in_transaction = False
        print("트랜잭션을 확정했습니다. COMMIT")

    def rollback_transaction(self):
        if not self.in_transaction:
            print("진행 중인 트랜잭션이 없습니다.")
            return
        self.conn.rollback()
        self.in_transaction = False
        print("트랜잭션을 취소했습니다. ROLLBACK")

    def show_indexes(self):
        sql = """
        SELECT tbl_name AS table_name,
               name AS index_name,
               sql AS create_sql
        FROM sqlite_master
        WHERE type = 'index'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY tbl_name, name;
        """
        self.print_rows(self.fetch_all(sql))

    def check_foreign_keys(self):
        self.conn.execute("PRAGMA foreign_keys = ON;")
        rows = self.fetch_all("PRAGMA foreign_key_check;")
        if not rows:
            print("외래키 정합성 점검 결과: 이상 없음")
        else:
            print("외래키 오류가 발견되었습니다.")
            self.print_rows(rows)

    def show_row_counts(self):
        tables = self.fetch_all("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name;
        """)

        output = []
        for row in tables:
            table_name = row["name"]
            count = self.fetch_all(
                f"SELECT COUNT(*) AS row_count FROM {quote_identifier(table_name)};"
            )[0]["row_count"]
            output.append({"table_name": table_name, "row_count": count})

        if not output:
            print("테이블이 없습니다.")
            return

        headers = ["table_name", "row_count"]
        widths = []
        for h in headers:
            widths.append(max(len(str(r[h])) for r in output + [{h: h}]))

        line = " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers)))
        print(line)
        print("-" * len(line))
        for r in output:
            print(" | ".join(str(r[h]).ljust(widths[i]) for i, h in enumerate(headers)))

    def export_select_to_csv(self):
        print("\nCSV로 저장할 SELECT SQL을 입력하세요.")
        print("마지막 줄에 ; 만 입력하면 실행됩니다.")

        lines = []
        while True:
            line = input("SELECT SQL > ")
            if line.strip() == ";":
                break
            lines.append(line)

        sql = "\n".join(lines).strip()
        if not sql.lower().startswith(("select", "with")):
            print("CSV 저장은 SELECT 또는 WITH 쿼리만 가능합니다.")
            return

        filename = input("저장할 CSV 파일명 예: result.csv > ").strip()
        if not filename:
            filename = f"query_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        cur = self.conn.execute(sql)
        rows = cur.fetchall()

        if not rows:
            print("조회 결과가 없어 CSV를 생성하지 않았습니다.")
            return

        with open(filename, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(rows[0].keys())
            for row in rows:
                writer.writerow([row[key] for key in row.keys()])

        print(f"CSV 저장 완료: {filename}")

    def backup_database(self):
        backup_dir = Path("backup")
        backup_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"{self.db_path.stem}_backup_{timestamp}{self.db_path.suffix}"

        shutil.copy2(self.db_path, backup_path)
        print(f"DB 백업 완료: {backup_path}")


def main():
    print("DBA Console 실행")

    default_db = find_default_db()
    if default_db:
        print(f"기본 DB 파일 발견: {default_db}")
        db_path = input(f"사용할 DB 파일명 Enter={default_db} > ").strip() or default_db
    else:
        db_path = input("사용할 DB 파일명 예: 파리바게트.db > ").strip()

    if not db_path:
        print("DB 파일명이 입력되지 않아 종료합니다.")
        return

    console = DBAConsole(db_path)
    console.run()


if __name__ == "__main__":
    main()
