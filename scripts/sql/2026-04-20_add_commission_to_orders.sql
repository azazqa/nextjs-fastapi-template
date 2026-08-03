-- 주문(Order) 수수료 컬럼 추가
-- - 상품 별칭 매칭 시 확정되는 수수료(원)를 주문에 스냅샷 저장

ALTER TABLE orders
ADD COLUMN IF NOT EXISTS commission integer DEFAULT 0;

UPDATE orders
SET commission = 0
WHERE commission IS NULL;

