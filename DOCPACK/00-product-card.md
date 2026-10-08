---
title: BookFinance — Product Card
doc_id: CARD-booktrading
doc_type: product-card
verdict: invest
version: 0.1
date: 2026-10-08
status: ร่างเพื่อพิจารณา
owner: Product owner (Book Dev)
---

# BookFinance — Product Card

## 1. สรุปคุณค่าในหนึ่งประโยค

ศูนย์บัญชาการการเงินที่ช่วยเจ้าของปกป้องทุนก่อนให้บอทเทรดด้วยเงินจริง โดยตั้งค่าเริ่มต้นเป็น observe-only และให้ evidence gate เป็นตัวตัดสิน

## 2. ปัญหาและผู้ใช้เป้าหมาย

- ปัญหา: บอทเทรดส่วนใหญ่ข้ามไปสู่ "เทรดได้" โดยไม่มีหลักฐานว่าควรใช้เงินจริงหรือไม่ ทำให้เสียทุน
- ผู้ใช้เป้าหมาย: เจ้าของ (ผู้ใช้คนเดียว) ที่ทำ paper trading คริปโตและ prediction market; ใช้เป็น Tier A interview flagship ด้วย
- ผู้ใช้ภายนอกหรือลูกค้าที่จ่ายเงิน: ไม่มีหลักฐาน **[ต้องยืนยัน]**

## 3. สิ่งที่ทำได้จริงตอนนี้

- Backend Go (`backend/cmd/main.go`, `backend/internal/{adapter,domain,port}`) พร้อม migrations 39 ไฟล์และ gRPC (`proto/trading.proto`)
- Strategy layer Python (`strategy/app/`): `grid_bot.py`, `dca_bot.py`, `futures_bot.py`, `arbitrage.py`, `backtester.py`, `risk_manager.py`, `paper_execution.py`, `polymarket/`, `market_intel/`
- Frontend Next.js 15.5 / React 19 (`frontend/src`, 157 ไฟล์) ที่อ่าน `/api/command-center` เป็นแหล่งความจริงเดียว; หน้าที่มีปุ่มเทรดซ่อนหลัง `NEXT_PUBLIC_ADVANCED_UI`
- Kill switch และ dry-run (`POLY_DRY_RUN=true`) — README รายงานว่าบอทหยุดอยู่ที่ drawdown 15.84% ของ paper bankroll **[ต้องยืนยัน]** ว่าตัวเลขยังเป็นปัจจุบัน
- Docker Compose (dev/prod), Caddy และ monitoring; deploy production ต้องสั่ง `workflow_dispatch` เอง

## 4. หลักฐานสถานะ

- Stack: Go (backend, gRPC), Python (strategy), Next.js 15.5 / React 19 (frontend), Docker Compose
- Commits: 117 (แรก 2026-03-27 / ล่าสุด 2026-10-01), branch `main`
- Source: 508 ไฟล์ / 140846 บรรทัด; test files: 109
- CI workflows: 1; deploy config: `docker-compose.yml`
- Live URL: ไม่มี
- README: 404 บรรทัด ("📘 BookFinance - AI Financial Command Center"); template family size: 1

## 5. คุณค่าและจุดต่าง

- จุดต่างหลัก: ฟีเจอร์แกนคือการ *พิสูจน์ว่ายังไม่ควรเทรด* (evidence gate + kill switch) แทนการโชว์ว่าเทรดได้
- สถาปัตยกรรมหลายภาษามีเหตุผล: Go สำหรับ API/WebSocket/gRPC, Python สำหรับกลยุทธ์และการพยากรณ์
- Test 109 ไฟล์ข้าม frontend (Vitest รวม contract test ของ `/api/command-center`), Python และ Go
- **[สมมติฐาน]** มุมรายได้อาจมาจากการขาย template/คอร์ส "safe trading bot" หรือเป็นเครื่องมือส่วนตัวที่ลดการขาดทุน — ยังไม่มีหลักฐาน

## 6. ช่องว่างสำคัญ

- ไม่มีผลตอบแทนที่พิสูจน์ได้; paper bankroll ติดลบตามที่ README รายงาน
- ขอบเขตกว้างมาก (32 หน้า dashboard, 140k บรรทัด) ทำให้ดูแลยากสำหรับคนเดียว
- ไม่มี live URL สาธารณะ; สถานะ server ที่รันอยู่ **[ต้องยืนยัน]**
- มี repo พี่น้อง `bookchaowalit-trading-backend` ที่ทับซ้อน (exchange connector, grid strategy)

## 7. คำตัดสิน

**invest** — เป็น repo เดียวในกลุ่มนี้ที่มี core ทำงานจริง, test จริง, ระบบความปลอดภัยของทุนที่ใช้งานอยู่ และอยู่ใน Tier A ของ portfolio เงื่อนไขที่จะเปลี่ยนคำตัดสิน: ถ้าเจ้าของเลิกใช้งานจริงและไม่ใช้ในการสัมภาษณ์อีก ให้ลดเป็น `showcase`

## 8. ขั้นต่อไป

1. ยกระดับเป็น L1 docpack (PRD + architecture + runbook) จาก README/RUNBOOK ที่มีอยู่
2. รวม connector ที่ไม่ซ้ำจาก `bookchaowalit-trading-backend` (InnovestX, `thai_stock_strategy.py`) หรือบันทึกว่าไม่ต้องการ
3. ตัดหน้า dashboard ที่ซ่อน/เลื่อนไว้ (11 route ตาม README) เพื่อลดภาระดูแล

## การอนุมัติ

| บทบาท | การตัดสินใจ | วันที่ |
|---|---|---|
| Product owner (Book Dev) | [ต้องยืนยัน] verdict `invest` | — |

## แหล่งข้อมูล

- `bookchaowalit-ai/book-products/booktrading/README.md`
- `bookchaowalit-ai/book-products/booktrading/PRODUCT.md`
- `bookchaowalit-ai/book-products/booktrading/backend/go.mod`
- `bookchaowalit-ai/book-products/booktrading/backend/cmd/main.go`
- `bookchaowalit-ai/book-products/booktrading/strategy/app/`
- `bookchaowalit-ai/book-products/booktrading/frontend/package.json`
- `bookchaowalit-ai/book-products/booktrading/.github/workflows/ci-cd.yml`
- `repository-catalog/policies/BOOK-DEV-TIER-LABELS.md`
