-- 정산(Settlement) 수수료 컬럼 추가
-- - 배송 처리 시 생성되는 정산 대기 레코드에 주문 수수료를 스냅샷 저장

ALTER TABLE settlements
ADD COLUMN IF NOT EXISTS commission integer DEFAULT 0;

UPDATE settlements
SET commission = 0
WHERE commission IS NULL;

