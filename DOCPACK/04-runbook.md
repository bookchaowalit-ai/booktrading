---
title: BookFinance — Runbook การติดตั้งและดูแลระบบ
doc_id: BTR-DOC-04
doc_type: runbook
version: 0.1
date: 2026-10-08
status: ร่างเพื่อพิจารณา
owner: DevOps / Operator (Book Dev)
related: 02-architecture.md, 03-nfr-security.md, 07-test-uat.md
---

# BookFinance — Runbook การติดตั้งและดูแลระบบ

> Runbook นี้สรุปจาก `README.md`, `PRODUCTION.md` และ `strategy/RUNBOOK.md` สำหรับ decision tree ฉบับเต็มให้ใช้ `strategy/RUNBOOK.md` เป็นหลัก

## 1. Environments

| Env | ที่อยู่ | วิธีรัน | สถานะ |
|---|---|---|---|
| local dev | เครื่องผู้พัฒนา | `docker compose up -d --build` (`docker-compose.yml`, `docker-compose.dev.yml`) | ใช้งานอยู่ (evidence log 2026-08-11 ระบุ bootstrap local redis+postgres) |
| CI | GitHub Actions | `.github/workflows/ci-cd.yml` | ใช้งานอยู่ |
| production | VPS `/opt/bookfinance` | `docker-compose.prod.yml` + Caddy | ยังไม่มี **[ต้องยืนยัน]** |

พอร์ต local: Frontend `http://localhost:3001`, Backend `http://localhost:8080`, Strategy `http://localhost:8000` (`README.md` Quick Start)

## 2. Build / deploy

```bash
# local
docker compose up -d --build

# production (บนเซิร์ฟเวอร์ หลังเตรียม env แล้ว)
./deploy.sh production
# หรือ
docker compose -f docker-compose.prod.yml up -d --build
```

CI deploy: Actions → `CI/CD Pipeline` → `workflow_dispatch` และติ๊ก `deploy_production=true` บน `main` จากนั้น job `deploy` SSH ไปที่โฮสต์แล้ว `git pull` + `docker compose ... up -d --build` ต้องผ่าน Gate 4 ใน `docs/READINESS_CHECKLIST.md` ก่อน

## 3. Config / secret (ชื่อตัวแปรเท่านั้น)

| กลุ่ม | ตัวแปร |
|---|---|
| Database | `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_USER`, `DATABASE_PASSWORD`, `DATABASE_NAME`, `DATABASE_SSLMODE`, `DATABASE_URL`, `DB_PASSWORD` |
| Redis | `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_DB` |
| Server | `SERVER_PORT`, `WS_PORT`, `GRPC_PORT`, `SERVER_READ_TIMEOUT`, `SERVER_WRITE_TIMEOUT`, `WS_MAX_CLIENTS`, `WS_BROADCAST_QUEUE`, `TLS_CERT_FILE`, `TLS_KEY_FILE`, `ENVIRONMENT`, `FRONTEND_URL`, `TRUSTED_PROXIES` |
| Auth | `ENCRYPTION_KEY`, `AUTH_TOKEN`, `FIRST_ADMIN_EMAIL`, `FIRST_ADMIN_NAME`, `FIRST_ADMIN_PASSWORD`, `ALLOW_REGISTRATION`, `REGISTRATION_INVITE_CODE` |
| Strategy proxy | `STRATEGY_URL`, `STRATEGY_PROXY_TIMEOUT`, `BACKEND_API_BASE`, `PAPER_API_BASE` |
| Exchange | `EXCHANGE_PROVIDER`, `BINANCE_TH_API_KEY`, `BINANCE_TH_API_SECRET`, `BINANCE_API_KEY`, `BINANCE_API_SECRET`, `BINANCE_USE_TESTNET`, `BITKUB_API_KEY`, `BITKUB_API_SECRET`, `BITKUB_USE_TESTNET`, `BINANCE_FUTURES_API_KEY`, `BINANCE_FUTURES_API_SECRET` |
| Safety flags | `POLY_DRY_RUN` (ต้องเป็น `true`), `FUTURES_ENABLED`, `FUTURES_EXECUTION_MODE` (`paper`/`testnet`) |
| DEX/on-chain | `DEX_ENABLED`, `DEX_PROVIDER`, `DEX_CHAIN_ID`, `DEX_GAS_LIMIT`, `DEX_SLIPPAGE_PCT`, `DEX_MAX_PRICE_IMPACT`, `ETH_RPC_URL`, `BSC_RPC_URL`, `ARBITRUM_RPC_URL`, `BASE_RPC_URL` |
| Notification | `TELEGRAM_BOT_TOKEN` |
| Frontend | `NEXT_PUBLIC_ADVANCED_UI` |
| Logging | `LOG_LEVEL`, `LOG_FORMAT` |
| CI secrets | `PRODUCTION_HOST`, `PRODUCTION_USER`, `SSH_PRIVATE_KEY` |

ค่าจริงเก็บใน secret store ส่วนตัวเท่านั้น ห้าม commit `.env`

## 4. Health check

```bash
curl -s http://localhost:8080/api/health          # backend
curl -s http://localhost:8000/api/health          # strategy
docker compose ps
docker compose exec strategy python /app/scripts/monitor.py   # decision block รายวัน
```

ผลที่คาดหวังของ monitor ในโหมดปัจจุบัน: decision `WAIT` จนกว่า gate จะผ่าน บันทึกผลลง `docs/EVIDENCE_LOG.md`

## 5. Emergency stop

```bash
docker compose stop strategy
# หรือ
docker compose exec redis redis-cli SET poly_paper:kill_override 1
```

Grid จริง: `POST /api/real-grid/kill` (ต้องเป็น admin)

## 6. Rollback

1. Redeploy tag/commit ก่อนหน้า: `git checkout <tag>` แล้ว `docker compose -f docker-compose.prod.yml up -d --build`
2. Migration ที่ไม่มี `.down.sql` (`013`, `014`, `018`, `019`, `020`) ถือเป็น one-way ต้อง restore จาก backup แทน
3. เปิด safety ก่อน rollback: ให้ `POLY_DRY_RUN=true` และ kill switch ACTIVE

## 7. Incident / troubleshooting

| อาการ | ตรวจ | แก้ |
|---|---|---|
| Service ไม่ขึ้น | `docker compose logs -f <service>` | ดู `PRODUCTION.md` §Troubleshooting |
| ต่อ DB ไม่ได้ | `docker compose exec postgres pg_isready` | ตรวจ `DATABASE_*` |
| SSL ไม่ออก | log ของ caddy | ตรวจ DNS และโดเมนใน `Caddyfile` |
| Dashboard แสดง 403 | role ของผู้ใช้ | route write ของ `/strategy-api` ต้องเป็น admin |
| Kill switch ทำงาน | monitor | **ห้าม reset** จนกว่า decision tree บอก GO (`strategy/RUNBOOK.md` §When NOT to Reset) |

## 8. Backup / restore

```bash
# backup (ตาม PRODUCTION.md §Step 6)
docker exec bookfinance-postgres pg_dump -U trading trading_bot | gzip > db_<date>.sql.gz
docker cp bookfinance-redis:/data/dump.rdb redis_<date>.rdb

# restore (ขั้นตอนเสนอ) [สมมติฐาน]
gunzip -c db_<date>.sql.gz | docker exec -i bookfinance-postgres psql -U trading trading_bot
```

Cron backup บนโฮสต์จริงยังไม่มีหลักฐาน **[ต้องยืนยัน]**; ยังไม่เคยทดสอบ restore **[ต้องยืนยัน]**

## การอนุมัติ

| บทบาท | สถานะ | วันที่ | ลงนาม |
|---|---|---|---|
| DevOps / Operator | รอตรวจ | — | [ต้องยืนยัน] |

## แหล่งข้อมูล

- `README.md` (Quick Start, Configuration, Monitoring), `PRODUCTION.md`, `RUNBOOK.md`, `strategy/RUNBOOK.md`
- `deploy.sh`, `docker-compose*.yml`, `Caddyfile`, `.github/workflows/ci-cd.yml`
- `backend/internal/config/config.go`, `backend/cmd/main.go`, `backend/internal/adapter/http/`
- `docs/READINESS_CHECKLIST.md`, `docs/EVIDENCE_LOG.md`
