# 주문 raw 채널별 다운로드 (운영/성능 메모)

## 목적

- 주문 목록 화면의 검색 조건을 그대로 유지한 채, **특정 채널의 주문**을 `orders.raw` 기반으로 엑셀로 다운로드한다.
- **컬럼 미스매칭**을 피하기 위해 주문은 생성 시점의 채널 엑셀 매핑 버전을 FK로 고정하고, 다운로드는 **버전별로 파일을 분리**한다.

## 다운로드 포맷 규칙

- **단일 파일**: xlsx
- **다건 파일**(아래 중 하나라도 해당): zip(xlsx 묶음)
  - 동일 채널 내 **매핑 버전이 2개 이상**
  - (향후) 건수/용량 기준으로 **파일 분할(청크)** 이 필요한 경우

## 1만 건+ 부하 검토(권장)

### DB 쿼리

- 페이지네이션 반복 대신 `id` 기준 **청크 조회**(예: 2,000행 단위)로 메모리/락 부담을 줄인다.
- `orders.channel_id`, `orders.channel_mapping_version_id`, `orders.status`, `orders.order_date` 등에 인덱스가 필요할 수 있다.

### 엑셀 생성

- `openpyxl`은 대량 작성 시 메모리 사용이 커질 수 있어 `Workbook(write_only=True)`를 기본으로 사용한다.
- 셀 값은 원칙적으로 문자열/숫자/빈 값으로 단순화한다(객체/배열은 JSON 문자열로 직렬화).

### 동기/비동기 기준

- **동기(HTTP 즉시 응답)**: 최대 건수 상한(예: 10,000) 이하
- **비동기 배치**: 상한 초과 또는 zip+분할이 필요한 경우

## 비동기 배치(후속)

### 흐름

1. export job 생성: `POST /orders/export/raw-by-channel/jobs`
2. job 상태 조회: `GET /orders/export/raw-by-channel/jobs/{id}`
3. 완료 시 다운로드: `GET /orders/export/raw-by-channel/jobs/{id}/download`

### 저장

- 결과 파일은 로컬 디스크 또는 오브젝트 스토리지에 저장하고, 만료(`expires_at`)를 둔다.

## ZIP 묶기(후속)

- 버전별 xlsx + (필요 시) 청크 분할 xlsx를 `zipfile`로 묶어 단일 zip으로 내려준다.

