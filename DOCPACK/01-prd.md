---
title: BookFinance — Product Requirements (PRD)
doc_id: BTR-DOC-01
doc_type: prd
version: 0.1
date: 2026-10-08
status: ร่างเพื่อพิจารณา
owner: Product owner (Book Dev)
related: 00-overview.md, 00-product-card.md, 02-architecture.md, 05-srs.md, 08-rtm.md
---

# BookFinance — Product Requirements (PRD)

> ขอบเขต: ผลิตภัณฑ์ตามที่มีในโค้ด ณ commit ล่าสุด 2026-10-01 เอกสารนี้ **ไม่ใช่** การอนุมัติให้เทรดด้วยเงินจริง ทุกตัวเลขผลการเทรดเป็นของ paper bankroll

## 1. ปัญหาและเป้าหมาย

### 1.1 ปัญหา

| # | ปัญหา | ผลกระทบ |
|---|---|---|
| PB-1 | บอทเทรดทั่วไปข้ามจาก "เทรดได้" ไปสู่การใช้เงินจริงโดยไม่มีหลักฐานว่ากลยุทธ์มี edge | เสียทุนจริง |
| PB-2 | ข้อมูลกระจายหลายแหล่ง (exchange, Polymarket, paper bot, grid bot) ทำให้ตัดสินใจจากตัวเลขที่ไม่ตรงกัน | เผลอใช้ risk source ผิดตัวในการปลด gate (`strategy/RUNBOOK.md` §Risk Sources) |
| PB-3 | UI ที่มีปุ่ม Start/Trade เด่นชวนให้ลงมือก่อนมีหลักฐาน | การตัดสินใจตามอารมณ์ |

### 1.2 เป้าหมาย

| ID | เป้าหมาย | ตัวชี้วัด | ค่าเป้าหมาย |
|---|---|---|---|
| G-1 | ปกป้องทุน | จำนวนคำสั่งเงินจริงที่ออกไปโดยไม่ผ่าน Gate 3 | 0 (ตามกฎใน `strategy/RUNBOOK.md` §Rules) |
| G-2 | ตัดสินใจจากแหล่งความจริงเดียว | หน้า Core 5 อ่านจาก `/api/command-center` และ endpoint ที่เกี่ยวข้อง | 100% ของหน้า Core 5 **[ต้องยืนยัน]** |
| G-3 | สร้างหลักฐานก่อนเลื่อน gate | Gate 0: สัญญาณ ≥ 100 รายการจาก ≥ 3 แหล่ง, ความแม่นยำ 24h > 45% | ตาม `docs/READINESS_CHECKLIST.md` |
| G-4 | เป็นงาน flagship ที่ตรวจซ้ำได้ | CI เขียวทั้ง 3 ชุด (Go, frontend, strategy) | ทุก push ไป `main` **[ต้องยืนยัน]** สถานะ CI ล่าสุด |

## 2. ผู้ใช้ / persona

| ID | Persona | เป้าหมาย | หลักฐาน |
|---|---|---|---|
| P-OP | เจ้าของ/operator คนเดียว | ดูสถานะทุนรายวัน, ตัดสินใจเลื่อน gate, ศึกษาตลาด | `strategy/RUNBOOK.md` §Daily Monitor |
| P-REV | ผู้ประเมิน portfolio/ผู้สัมภาษณ์ | ตรวจคุณภาพวิศวกรรมและแนวคิด safety | `PRODUCT.md` |
| P-EXT | ผู้ใช้ภายนอกหลายคน | ยังไม่มี; roadmap ระบุ "Multi-user support with RBAC" | **[สมมติฐาน]** ไม่ใช่เป้าหมายระยะสั้น |

## 3. ขอบเขต

### 3.1 In scope (มีในโค้ดแล้ว)

- Dashboard observe-only 5 หน้า (Today, Evidence, Research, System, Daily Report) สองภาษา TH/EN
- Polymarket paper bot พร้อม kill switch, dry-run, blocklist/allowlist และ monitor decision tree
- Paper/testnet สำหรับ grid (5 คู่), DCA, futures USDⓈ-M (paper/testnet เท่านั้น), arbitrage paper bot
- Backtest แบบ deterministic (grid, Spot vs Futures 1x–5x, walk-forward)
- Market intel / research / signal tracker
- โมดูลการเงินส่วนตัว (net worth, accounts, transactions, budgets) ใน backend
- Auth: login + lockout, registration แบบ gated, สิทธิ์ user/admin/service, proxy `/strategy-api`
- CI และ Docker Compose (dev/prod) + Caddy

### 3.2 Out of scope (ตอนนี้)

- การเทรดเงินจริงอัตโนมัติจนกว่า Gate 3 ผ่าน
- Futures mainnet, COIN-M, margin borrowing, options, leveraged tokens, CFD (`README.md`)
- Multi-user/RBAC เต็มรูปแบบ, mobile app, copy trading แบบใช้งานจริง (roadmap ยังไม่ติ๊ก)
- คำแนะนำการลงทุนสำหรับบุคคลภายนอก

## 4. ฟีเจอร์หลักและลำดับความสำคัญ

| ID | ฟีเจอร์ | Priority | สถานะ | อ้างอิง FR |
|---|---|---|---|---|
| F-01 | Command Center (decision, kill switch, ทุน, trigger ถัดไป) | Must | มีแล้ว | FR-01 |
| F-02 | Kill switch + dry-run + safety filters | Must | มีแล้ว | FR-06, FR-07 |
| F-03 | Readiness gates และ evidence log | Must | มีแล้ว (เอกสาร + `/api/evidence`) | FR-02, FR-14 |
| F-04 | Auth และ route access matrix | Must | มีแล้ว | FR-11, FR-12 |
| F-05 | Research / market intel / signal tracker | Should | มีแล้ว | FR-03 |
| F-06 | System health + daily report | Should | มีแล้ว | FR-04, FR-05 |
| F-07 | Paper engines (grid, DCA, Polymarket, arbitrage) | Should | มีแล้ว | FR-08 |
| F-08 | Futures paper/testnet + preflight | Could | มีแล้ว (ล็อก mainnet) | FR-09 |
| F-09 | Backtest และ walk-forward | Should | มีแล้ว | FR-10 |
| F-10 | Advanced UI (หน้าเทรด) | Could | ซ่อนหลัง flag | FR-13 |
| F-11 | โมดูลการเงินส่วนตัว | Could | มี API; การใช้งานจริง **[ต้องยืนยัน]** | FR-16 |
| F-12 | Exchange integration (Binance TH, Bitkub, Binance Global) | Could | มี adapter; ใช้เงินจริงถูกบล็อก | FR-17 |
| F-13 | Alerts / Telegram / webhook | Could | มีโค้ด | FR-18 |

## 5. ตัวชี้วัดความสำเร็จ

| ID | ตัวชี้วัด | วิธีวัด | เป้าหมาย |
|---|---|---|---|
| M-1 | วันที่รัน monitor และบันทึกสถานะ | จำนวน entry ใน `docs/EVIDENCE_LOG.md` ต่อสัปดาห์ | **[ต้องยืนยัน]** เจ้าของกำหนด (runbook บอก "Monitor daily") |
| M-2 | ความแม่นยำสัญญาณ | `GET /api/signal-tracker/stats` | 24h > 45%, 7d > 40% (Gate 0) |
| M-3 | Paper drawdown | `/api/command-center` | ≤ 5% ก่อนพิจารณาเลื่อน Gate 1 |
| M-4 | ความสมบูรณ์ของ test | CI 3 ชุดผ่าน | 100% |
| M-5 | ผลตอบแทนจริง | — | ไม่มีหลักฐาน; ไม่ตั้งเป้าจนกว่าจะผ่าน Gate 3 |

## 6. Roadmap / phase

| Phase | สิ่งที่ต้องเกิด | เงื่อนไขผ่าน | สถานะ |
|---|---|---|---|
| P0 Capital protection (ปัจจุบัน) | WAIT, เก็บสัญญาณ | Gate 0 | กำลังดำเนินการ |
| P1 Dry-run | เปิด `POLY_DRY_RUN=true` 2–4 สัปดาห์ | Gate 1 | ยังไม่พร้อม |
| P2 Reset paper | รีเซ็ต kill switch และ paper cycle ใหม่ | Gate 2 | ยังไม่พร้อม |
| P3 Micro-live | เงินจริงจำนวนเล็ก | Gate 3 | ยังไม่พร้อม |
| P4 Production deploy | โดเมน, secret, backup, monitoring | Gate 4 | ยังไม่พร้อม |
| Housekeeping | ตัด route ที่ซ่อน, ตัดสินใจเรื่อง repo พี่น้อง `bookchaowalit-trading-backend` | — | ตาม `00-product-card.md` §8 |

## 7. ข้อสมมติฐานและความเสี่ยง

| ID | ประเภท | รายละเอียด | การจัดการ |
|---|---|---|---|
| A-1 | สมมติฐาน | ผู้ใช้มีคนเดียวและไม่มีแผนเปิดให้คนอื่นใช้ในระยะสั้น **[สมมติฐาน]** | ทบทวนเมื่อเริ่ม RBAC |
| A-2 | สมมติฐาน | ตัวเลข paper bankroll ใน README/RUNBOOK เป็นสถานะล่าสุด **[ต้องยืนยัน]** | รัน `scripts/monitor.py` แล้วบันทึกใน evidence log |
| R-1 | ความเสี่ยง | ขอบเขตกว้าง (32 หน้า dashboard, ~140k บรรทัด) เกินกำลังผู้ดูแลคนเดียว | ตัดหน้า hidden/deferred 11 route |
| R-2 | ความเสี่ยง | Money math ใช้ `float`/`float64` | backlog P1 ใน `docs/UPGRADE-PLAN.md` |
| R-3 | ความเสี่ยง | CI pin Go 1.21 (EOL) | backlog P1 ใน `docs/UPGRADE-PLAN.md` |
| R-4 | ความเสี่ยง | การ backtest ที่เป็นบวกถูกตีความเป็นใบอนุญาตเทรด | runbook ระบุชัดว่าเป็นหลักฐานสำหรับ paper เท่านั้น |
| R-5 | ความเสี่ยง | repo พี่น้องทับซ้อน ทำให้แก้สองที่ | ตัดสินใจ merge หรือ archive |

## การอนุมัติ

| บทบาท | สถานะ | วันที่ | ลงนาม |
|---|---|---|---|
| Product owner (Book Dev) | รอตรวจ | — | [ต้องยืนยัน] |

## แหล่งข้อมูล

- `README.md` (Current Operating Mode, Features, Leveraged Market Scope, Roadmap)
- `PRODUCT.md`
- `strategy/RUNBOOK.md` (Decision Tree, Rules)
- `docs/READINESS_CHECKLIST.md`, `docs/UPGRADE-PLAN.md`, `docs/EVIDENCE_LOG.md`
- `strategy/infrastructure/api/app.py`, `backend/internal/adapter/http/handler.go`
- `DOCPACK/00-product-card.md`
