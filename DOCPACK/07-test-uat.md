---
title: BookFinance — Test Strategy และ UAT
doc_id: BTR-DOC-07
doc_type: test-uat
version: 0.1
date: 2026-10-08
status: ร่างเพื่อพิจารณา
owner: QA (Book Dev)
related: 03-nfr-security.md, 05-srs.md, 08-rtm.md
---

# BookFinance — Test Strategy และ UAT

## 1. ระดับการทดสอบ

| ระดับ | เครื่องมือ | ขอบเขต | จำนวนไฟล์ (นับ 2026-10-08) |
|---|---|---|---|
| Unit/Integration (Go) | `go test -race` | domain service (grid, paper engine, bot safety, finance), auth, route access, proxy, exchange reconcile, DEX, users DB | 24 ไฟล์ `*_test.go` |
| Unit (Python strategy) | `pytest` (ไม่รวม marker `integration`) + research tests แบบ stdlib | kill switch, safety filters, monitor decision, futures safety, backtest, route access, auth, portfolio, on-chain | 60 ไฟล์ใน `strategy/tests/` |
| Unit/Contract (frontend) | Vitest | API service, auth role/config, forbidden, ErrorBoundary, SystemHealthCheck, LoginModal, contract `/api/command-center` | 9 ไฟล์ |
| E2E | Playwright | landing | 1 spec (`frontend/e2e/landing.spec.ts`) — ไม่ได้รันใน CI |
| Contract (live) | `pytest -m integration` | `test_command_center_contract.py` กับ service ที่รันอยู่ | รันเอง |
| Static | gofmt, go vet, go mod tidy, eslint, `tsc --noEmit`, ruff | ทั้ง 3 ภาษา | ใน CI |
| UAT | operator ตรวจตาม checklist ด้านล่าง | Core 5 + safety | ยังไม่มีบันทึก **[ต้องยืนยัน]** |

## 2. สภาพแวดล้อม

- CI: GitHub Actions ubuntu-latest พร้อม service TimescaleDB pg16 และ Redis 7 สำหรับ Go test; Node 24; Python 3.11
- Local: `docker compose exec strategy pytest /app/tests/ -v`, `docker compose exec backend go test -v ./...`, `docker compose exec frontend npm test`, หรือ `./scripts/test.sh` **[ต้องยืนยัน]** ว่า `scripts/test.sh` มีอยู่ (ไดเรกทอรี `scripts/` ปัจจุบันมีเพียง `migrate.sh`)

## 3. Test cases

| ID | FR | กรณีทดสอบ | ผลคาดหวัง | หลักฐานอัตโนมัติ |
|---|---|---|---|---|
| TC-01 | FR-01 | เรียก `/api/command-center` | มี decision, kill switch, capital, next triggers ตาม contract | `frontend/src/test/contract.test.ts`, `strategy/tests/test_command_center_contract.py` (integration) |
| TC-02 | FR-06 | paper drawdown เกินเกณฑ์ | kill switch ACTIVE ไม่มี entry ใหม่ | `test_kill_switch.py` |
| TC-03 | FR-06 | reset kill switch โดยไม่ auth | ถูกปฏิเสธ | `test_safety_reset_auth.py` |
| TC-04 | FR-07 | `POLY_DRY_RUN=true` | ไม่ส่ง order จริง; safety filter กรอง blocklist | `test_safety_filters.py`, `test_mainnet_default.py` |
| TC-05 | FR-09 | ตั้ง futures เป็น mainnet | engine ปฏิเสธ; leverage > 5x ถูกจำกัด | `test_futures_safety.py` |
| TC-06 | FR-10 | รัน futures backtest | ผลแยก in-sample/holdout, deterministic | `test_futures_backtest.py`, `research/tests/futures_backtest_test.py`, `walk_forward_test.py` |
| TC-07 | FR-08 | grid ส่ง order ซ้ำ/ผลไม่ชัด | reconcile ด้วย client order ID ไม่ส่งซ้ำ | `grid_reconcile_test.go`, `order_reconcile_test.go`, `test_grid_safety.py`, `test_dca_order_grid.py` |
| TC-08 | FR-11 | login ผิดหลายครั้งจาก IP เดียว | ถูก lock ต่อ (email, IP) | `login_lockout_test.go` |
| TC-09 | FR-11 | สมัครเมื่อปิด registration | ถูกปฏิเสธ; ต้องมี invite code ถ้ากำหนด | `registration_test.go` |
| TC-10 | FR-11 | เรียก route ทุกตัวด้วยแต่ละ role | ได้ผลตามตาราง access | `routes_access_test.go`, `auth_boundary_test.go`, `test_route_access_matrix.py`, `test_mutating_routes_auth.py` |
| TC-11 | FR-12 | write ผ่าน `/strategy-api` ด้วย user ธรรมดา | 403; admin ผ่านและ token ไม่ส่งถึง browser | `strategy_proxy_test.go`, `strategy-services-auth.test.ts` |
| TC-12 | FR-14 | สถานะต่าง ๆ ป้อนเข้า monitor | decision ตาม decision tree | `test_monitor_decision.py` (28 test) |
| TC-13 | FR-04 | component ล่ม | หน้า System แสดงสถานะผิดปกติ | `SystemHealthCheck.test.tsx` |
| TC-14 | FR-16 | ผู้ใช้อ่าน/แก้ finance ของคนอื่น | ถูกปฏิเสธ | `finance_account_auth_test.go`, `finance_transaction_auth_test.go`, `finance_resource_auth_test.go` |
| TC-15 | FR-13 | ไม่ตั้ง `NEXT_PUBLIC_ADVANCED_UI` | เมนูไม่แสดงหน้าเทรด | ไม่มี test อัตโนมัติ — UAT ด้วยมือ |
| TC-16 | FR-02, FR-03, FR-05 | เปิด Evidence/Research/Daily Report | แสดงข้อมูลหรือ empty state ไม่ crash | ไม่มี test เฉพาะ — UAT ด้วยมือ |
| TC-17 | FR-15 | สลับ `/th` และ `/en` | ข้อความเปลี่ยนภาษาครบ | ไม่มี test เฉพาะ — UAT ด้วยมือ |
| TC-18 | FR-18 | kill switch ทำงาน | ได้แจ้งเตือน webhook/Telegram | ไม่มีหลักฐาน **[ต้องยืนยัน]** |

## 4. เกณฑ์ผ่าน (entry / exit)

- Entry: `docker compose up` สำเร็จ, `.env` ตั้งแบบ paper-only, ไม่มี key mainnet
- Exit สำหรับ merge: CI ทั้ง 3 job เขียว
- Exit สำหรับเลื่อน gate: เกณฑ์ใน `docs/READINESS_CHECKLIST.md` + บันทึกใน `docs/EVIDENCE_LOG.md`
- Exit สำหรับ production: Gate 4 ครบทุกข้อ และ UAT TC-15 ถึง TC-18 ผ่าน

## 5. หลักฐานที่มี

| หลักฐาน | วันที่ | ที่มา |
|---|---|---|
| Frontend `tsc`, `vitest` 36/36, `next build` ผ่าน | 2026-08-05 | `PRODUCT.md` |
| ทั้ง 3 ชุด (Go, Next.js, strategy) เขียว | ตาม pass ล่าสุด **[ต้องยืนยัน]** วันที่ | `docs/UPGRADE-PLAN.md` |
| Paper grid trial PASS (safety guards hold) | ดู entry ใน log | `docs/EVIDENCE_LOG.md` |
| รอบเขียนเอกสารนี้ (2026-10-08) | ไม่ได้รัน test — เครื่องนี้ไม่มี Python deps (`fastapi`) และ `frontend/node_modules`; Go test ต้องมี Postgres/Redis | — |

## การอนุมัติ

| บทบาท | สถานะ | วันที่ | ลงนาม |
|---|---|---|---|
| QA (Book Dev) | รอตรวจ | — | [ต้องยืนยัน] |

## แหล่งข้อมูล

- `.github/workflows/ci-cd.yml`
- `backend/internal/**/*_test.go`, `strategy/tests/`, `strategy/research/tests/`, `frontend/src/**/*.test.ts(x)`, `frontend/e2e/`
- `README.md` §Testing, `PRODUCT.md`, `docs/UPGRADE-PLAN.md`, `docs/EVIDENCE_LOG.md`, `docs/READINESS_CHECKLIST.md`
