
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS 브랜드 (
    브랜드코드   VARCHAR(20)  PRIMARY KEY,
    브랜드명     VARCHAR(50),
    제조사정보   VARCHAR(100)
);
CREATE TABLE IF NOT EXISTS 공급업체 (
    업체코드   VARCHAR(20)  PRIMARY KEY,
    업체명     VARCHAR(50),
    담당자명   VARCHAR(30),
    연락처     VARCHAR(20)
);
CREATE TABLE IF NOT EXISTS 지점 (
    지점명     VARCHAR(50)  PRIMARY KEY  NOT NULL,
    지역_시도  VARCHAR(20),
    주소       VARCHAR(100),
    직원_수    INT,
    영업시간   VARCHAR(50)
);
CREATE TABLE IF NOT EXISTS 상품 (
    상품코드   VARCHAR(20)  PRIMARY KEY,
    이름       VARCHAR(50),
    가격       INT          CHECK (가격 >= 0),
    제조일자   TEXT,
    유통기한   TEXT,
    브랜드코드 VARCHAR(20),
    FOREIGN KEY (브랜드코드) REFERENCES 브랜드(브랜드코드)
);
CREATE TABLE IF NOT EXISTS 빵 (
    상품코드     VARCHAR(20)  PRIMARY KEY,
    글루텐여부   INTEGER,
    알레르기정보 VARCHAR(100),
    FOREIGN KEY (상품코드) REFERENCES 상품(상품코드)
);
CREATE TABLE IF NOT EXISTS 케이크 (
    상품코드   VARCHAR(20)  PRIMARY KEY,
    사이즈_호  INT,
    콜라보여부 INTEGER,
    FOREIGN KEY (상품코드) REFERENCES 상품(상품코드)
);
CREATE TABLE IF NOT EXISTS 샐러드 (
    상품코드   VARCHAR(20)  PRIMARY KEY,
    칼로리     INT,
    드레싱종류 VARCHAR(30),
    FOREIGN KEY (상품코드) REFERENCES 상품(상품코드)
);
CREATE TABLE IF NOT EXISTS 음료 (
    상품코드   VARCHAR(20)  PRIMARY KEY,
    용량_ml    INT,
    온도옵션   VARCHAR(20),
    카페인여부 INTEGER,
    FOREIGN KEY (상품코드) REFERENCES 상품(상품코드)
);
CREATE TABLE IF NOT EXISTS 스낵 (
    상품코드     VARCHAR(20)  PRIMARY KEY,
    중량_g       INT,
    개별포장여부 INTEGER,
    FOREIGN KEY (상품코드) REFERENCES 상품(상품코드)
);
CREATE TABLE IF NOT EXISTS 원두커피류 (
    상품코드   VARCHAR(20)  PRIMARY KEY,
    로스팅농도 VARCHAR(20),
    원산지     VARCHAR(30),
    FOREIGN KEY (상품코드) REFERENCES 음료(상품코드)
);
CREATE TABLE IF NOT EXISTS 유제품류 (
    상품코드   VARCHAR(20)  PRIMARY KEY,
    유지방함량 NUMERIC,
    살균방식   VARCHAR(30),
    FOREIGN KEY (상품코드) REFERENCES 음료(상품코드)
);
CREATE TABLE IF NOT EXISTS 탄산음료류 (
    상품코드 VARCHAR(20)  PRIMARY KEY,
    당류함량 NUMERIC,
    탄산강도 VARCHAR(20),
    FOREIGN KEY (상품코드) REFERENCES 음료(상품코드)
);
CREATE TABLE IF NOT EXISTS 아동음료류 (
    상품코드     VARCHAR(20)  PRIMARY KEY,
    첨가영양소   VARCHAR(50),
    캐릭터콜라보 VARCHAR(50),
    FOREIGN KEY (상품코드) REFERENCES 음료(상품코드)
);
CREATE TABLE IF NOT EXISTS 양갱류 (
    상품코드 VARCHAR(20)  PRIMARY KEY,
    주재료   VARCHAR(30),
    당도등급 INT CHECK (당도등급 BETWEEN 1 AND 5),
    FOREIGN KEY (상품코드) REFERENCES 스낵(상품코드)
);
CREATE TABLE IF NOT EXISTS 초코과자류 (
    상품코드   VARCHAR(20)  PRIMARY KEY,
    카카오함량 INT,
    초콜릿종류 VARCHAR(30),
    FOREIGN KEY (상품코드) REFERENCES 스낵(상품코드)
);
CREATE TABLE IF NOT EXISTS 젤리류 (
    상품코드 VARCHAR(20)  PRIMARY KEY,
    식감     VARCHAR(20),
    과즙함량 INT CHECK (과즙함량 BETWEEN 0 AND 100),
    FOREIGN KEY (상품코드) REFERENCES 스낵(상품코드)
);
CREATE TABLE IF NOT EXISTS 쿠키류 (
    상품코드   VARCHAR(20)  PRIMARY KEY,
    베이킹방식 VARCHAR(30),
    밀가루종류 VARCHAR(30),
    FOREIGN KEY (상품코드) REFERENCES 스낵(상품코드)
);
CREATE TABLE IF NOT EXISTS 견과류 (
    상품코드   VARCHAR(20)  PRIMARY KEY,
    견과종류   VARCHAR(30),
    시즈닝종류 VARCHAR(30),
    FOREIGN KEY (상품코드) REFERENCES 스낵(상품코드)
);
CREATE TABLE IF NOT EXISTS 직원 (
    직원ID VARCHAR(20)  PRIMARY KEY,
    이름   VARCHAR(30)  NOT NULL,
    연락처 VARCHAR(20),
    급여   INT          CHECK (급여 > 0),
    입사일 TEXT,
    지점명 VARCHAR(50),
    FOREIGN KEY (지점명) REFERENCES 지점(지점명) ON UPDATE CASCADE
);
CREATE TABLE IF NOT EXISTS 고객 (
    고객ID VARCHAR(20)  PRIMARY KEY,
    이름   VARCHAR(30)
);
CREATE TABLE IF NOT EXISTS 회원 (
    고객ID           VARCHAR(20)  PRIMARY KEY,
    이메일           VARCHAR(100),
    주소             VARCHAR(100),
    가입일자         TEXT,
    정보제공동의여부 INTEGER,
    연락처           VARCHAR(20),
    비밀번호         VARCHAR(100),
    FOREIGN KEY (고객ID) REFERENCES 고객(고객ID) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS 비회원 (
    고객ID       VARCHAR(20)  PRIMARY KEY,
    임시식별여부 INTEGER,
    FOREIGN KEY (고객ID) REFERENCES 고객(고객ID) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS 동의내역 (
    고객ID   VARCHAR(20),
    동의항목 VARCHAR(50),
    동의일자 TEXT,
    동의여부 INTEGER,
    철회일자 TEXT,
    PRIMARY KEY (고객ID, 동의항목),
    FOREIGN KEY (고객ID) REFERENCES 회원(고객ID) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS 발주 (
    발주번호 VARCHAR(20)  PRIMARY KEY,
    발주일자 TEXT,
    상태     VARCHAR(10)  CHECK (상태 IN ('대기', '완료')),
    지점명   VARCHAR(50),
    업체코드 VARCHAR(20),
    FOREIGN KEY (지점명)   REFERENCES 지점(지점명),
    FOREIGN KEY (업체코드) REFERENCES 공급업체(업체코드)
);
CREATE TABLE IF NOT EXISTS 발주상세 (
    발주번호 VARCHAR(20),
    항목번호 INT,
    주문수량 INT,
    상품코드 VARCHAR(20),
    PRIMARY KEY (발주번호, 항목번호),
    FOREIGN KEY (발주번호) REFERENCES 발주(발주번호) ON DELETE CASCADE,
    FOREIGN KEY (상품코드) REFERENCES 상품(상품코드)
);
CREATE TABLE IF NOT EXISTS 공급내역 (
    공급번호 VARCHAR(20)  PRIMARY KEY,
    공급일시 TEXT,
    공급수량 INT,
    발주번호 VARCHAR(20),
    업체코드 VARCHAR(20),
    FOREIGN KEY (발주번호) REFERENCES 발주(발주번호),
    FOREIGN KEY (업체코드) REFERENCES 공급업체(업체코드)
);
CREATE TABLE IF NOT EXISTS 판매 (
    판매번호   VARCHAR(20)  PRIMARY KEY,
    판매일자   TEXT,
    총판매금액 INT,
    결제수단   VARCHAR(10)  CHECK (결제수단 IN ('현금', '카드', '간편결제')),
    직원ID     VARCHAR(20),
    고객ID     VARCHAR(20),
    지점명     VARCHAR(50),
    FOREIGN KEY (직원ID) REFERENCES 직원(직원ID),
    FOREIGN KEY (고객ID) REFERENCES 고객(고객ID),
    FOREIGN KEY (지점명) REFERENCES 지점(지점명)
);
CREATE TABLE IF NOT EXISTS 판매상세 (
    판매번호 VARCHAR(20),
    항목번호 INT,
    수량     INT CHECK (수량 > 0),
    상품코드 VARCHAR(20),
    판매단가 INT,
    PRIMARY KEY (판매번호, 항목번호),
    FOREIGN KEY (판매번호) REFERENCES 판매(판매번호) ON DELETE CASCADE,
    FOREIGN KEY (상품코드) REFERENCES 상품(상품코드)
);
CREATE TABLE IF NOT EXISTS 보유 (
    지점명       VARCHAR(50),
    상품코드     VARCHAR(20),
    재고수량     INT CHECK (재고수량 >= 0),
    최소재고기준 INT,
    매장가격     INT,
    PRIMARY KEY (지점명, 상품코드),
    FOREIGN KEY (지점명)   REFERENCES 지점(지점명),
    FOREIGN KEY (상품코드) REFERENCES 상품(상품코드)
);
CREATE TABLE IF NOT EXISTS 취급 (
    브랜드코드 VARCHAR(20),
    업체코드   VARCHAR(20),
    PRIMARY KEY (브랜드코드, 업체코드),
    FOREIGN KEY (브랜드코드) REFERENCES 브랜드(브랜드코드),
    FOREIGN KEY (업체코드)   REFERENCES 공급업체(업체코드)
);
CREATE TABLE IF NOT EXISTS 공급 (
    상품코드 VARCHAR(20),
    업체코드 VARCHAR(20),
    PRIMARY KEY (상품코드, 업체코드),
    FOREIGN KEY (상품코드) REFERENCES 상품(상품코드),
    FOREIGN KEY (업체코드) REFERENCES 공급업체(업체코드)
);
