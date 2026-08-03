## 주문 이력(History) 성능 가정 / 운영 체크

### 데이터 규모 가정
- **주문 수**: 하루 1,000건
- **기간**: 3년
- **주문 건수**: \(1000 \times 365 \times 3 = 1,095,000\)

### 이력 행 수(주문당 평균 이벤트 수)
실제 이벤트 수는 업무 플로우에 따라 달라집니다. 아래는 운영 판단용 범위입니다.

- **3건/주문(보수)**: \(1,095,000 \times 3 = 3,285,000\) rows
- **5건/주문(중간)**: \(1,095,000 \times 5 = 5,475,000\) rows

예시 이벤트
- 생성(created)
- 발주(placed)
- 배송대기(shipping_waiting)
- 배송(shipping)
- 취소(cancelled) 또는 일반 수정(updated/status_changed)

### 테이블 용량(대략)
행당 용량은 JSON 스냅샷(before/after) 크기에 크게 좌우됩니다.

- **메타 중심(상태/사유/유저/타임스탬프 위주)**: 약 350~700B/row
- **before/after JSON 포함(필드+items 스냅샷)**: 약 0.8~1.6KB/row

대략 추정(테이블+인덱스 포함, 운영 환경/인덱스 개수에 따라 변동):
- **메타 중심**: 약 1.5~4GB
- **JSON 포함**: 약 5~12GB

### 파티셔닝이 꼭 필요한가?
초기 규모(약 300만~550만 rows, 수 GB~10GB대)는 PostgreSQL에서 **일반 인덱스/쿼리 튜닝으로 운영 가능한 범위**인 경우가 많습니다.

즉, **처음부터 월 파티셔닝을 강제할 필요는 낮습니다.**\n
다만 아래 조건이면 파티셔닝 또는 아카이빙(월 단위 테이블 분리)을 검토합니다.

- 연간 증가량이 **1천만 rows 이상**으로 커질 때
- 데이터 보관 정책이 있어 **월 단위 삭제/보관(archive)** 가 잦을 때
- 최신 N일(예: 30일) 조회가 인덱스 튜닝 후에도 지속적으로 느릴 때

### 관측 지표(배포 후 2~4주)
테이블이 실제로 얼마나 커지는지, 어떤 쿼리가 느린지 관측 후 최적화를 결정합니다.

- **용량**: `pg_total_relation_size('order_histories')`
- **인덱스 사용률**: `pg_stat_user_indexes`
- **쿼리 지연(p95)**: APM/로그 기반으로 `/orders/{id}/histories`, `/orders/histories` 측정

### 인덱스 권장(초기)
- `(order_id, created_at DESC)`
- `(created_at DESC, id DESC)`
- `(action_type, created_at DESC)`
- `(update_user_id, created_at DESC)`
- `(to_status, created_at DESC)`

