# EVM provider release gate

สถานะ: bounded, read-only และปิดไว้โดยค่าเริ่มต้น
วันที่ตรวจ: 2026-09-08

เอกสารนี้เป็น release contract สำหรับ `EVMProviderIngestor` ก่อนผูก endpoint
จริงของ GoPlus, Honeypot, simulation, LP custody หรือ RPC เข้ากับ degen
watchlist. มันอนุญาตเฉพาะการอ่านหลักฐานและการจำลองที่ไม่ส่ง transaction; ไม่ได้
อนุญาตการซื้อขาย การ sign หรือการเปิดเผย credential

## ขอบเขตปัจจุบัน

- `EVMProviderIngestor` รับ endpoint จาก caller/deployment registry เท่านั้น
  และไม่อ่าน environment เพื่อสร้าง endpoint เอง; `MarketScanner` จะอ่าน
  registry จาก environment เฉพาะเมื่อเปิด source `degen` และตั้งค่า JSON นี้ไว้
- `EVMProviderRegistry.from_env()` อ่านได้เฉพาะ JSON ที่ไม่มี secret value;
  ต้องผ่าน `enabled=true`, `release_gate_approved=true` และ secret resolver
  ก่อนจึงจะ materialize endpoint. เมื่อ scanner โหลด registry จาก environment
  จะใช้ resolver แบบ bounded ที่ map เฉพาะ suffix ของ `secret_ref` ไปยัง
  `MARKET_INTEL_EVM_SECRET_<SUFFIX>`; production ควร inject resolver จาก secret
  manager โดยตรง
- ไม่มี endpoint จริงในค่าเริ่มต้น การ import/construct จึงไม่ทำ network call
- endpoint ที่เป็น required และล้มเหลวจะทำให้ gate เป็น
  `insufficient_evidence`; provider ที่ไม่ required ใช้เป็นข้อมูลเสริมเท่านั้น
- provenance เก็บ provider/adapter, scheme/host/path, เวลา, จำนวนครั้ง, status
  และ SHA-256 ของ response body โดยไม่เก็บ URL query, header หรือ raw payload
- API key/credential ต้องมาจาก secret binding ใน header; query key ที่สื่อถึง
  credential ถูกปฏิเสธตั้งแต่ config

## สิ่งที่ต้องมีใน endpoint registry

เจ้าของระบบต้องบันทึกข้อมูลต่อ endpoint ใน registry ที่ review ได้ โดยไม่เก็บ
secret value ไว้ใน Git, URL, log หรือ manifest:

| รายการ | หลักฐานที่ต้องมี |
|---|---|
| Identity | provider, adapter, chain/chain ID, upstream owner และ schema version |
| Coverage | token/security fields ที่ endpoint ครอบคลุม และข้อจำกัดของ protocol |
| Freshness | timeout, retry budget, rate/quota limit และ evidence max age |
| Independence | upstream จริง; API หลายชื่อที่ proxy เดียวกันนับเป็น source เดียว |
| Secret binding | ชื่อ secret reference, header mapping, rotation owner และ redaction test |
| Availability | health/error budget, status mapping และ incident contact |
| Reproducibility | fetched block/finality หรือ provider snapshot semantics |
| Cost | per-request quota, daily cap และ bounded candidate count |

ห้ามใช้ endpoint ที่ใส่ key, token, signature หรือ password ใน query string
และห้ามใช้ ticker/name เป็น identity แทน `chain + token_address`.

ตัวอย่าง registry ที่เก็บได้ใน environment หรือ deployment config:

```json
{
  "version": "evm-provider-registry.v1",
  "enabled": true,
  "release_gate_approved": false,
  "endpoints": [
    {
      "provider": "goplus",
      "adapter": "goplus",
      "url_template": "https://provider.example/security/{chain}/{token_address}",
      "supported_chains": ["ethereum", "base"],
      "independence_group": "goplus-upstream",
      "secret_ref": "secret://market-intel/goplus",
      "secret_header": "X-API-KEY",
      "required": true
    }
  ]
}
```

`independence_group` คือ upstream จริงที่ใช้คำนวณความเป็นอิสระของหลักฐาน
ถ้า API หลายชื่อชี้ไป backend เดียวกันให้ใช้ group เดียวกัน ระบบจะไม่เพิ่ม
`independent_provider_count` จากชื่อ provider เพียงอย่างเดียว

`release_gate_approved` ต้องเป็น `false` จนกว่า approval record ด้านล่างจะ
ครบ. ค่า secret จริงต้องมาจาก resolver ใน memory ระหว่างสร้าง
`EVMProviderEndpoint`; ห้ามเติมลงใน JSON, `.env`, URL หรือ Git

ตัวอย่าง `secret://market-intel/goplus` จะอ่านค่า runtime จาก
`MARKET_INTEL_EVM_SECRET_GOPLUS` เมื่อ scanner เป็นผู้โหลด registry อัตโนมัติ.
ชื่อ environment ถูกสร้างจากส่วนท้ายของ reference เท่านั้น; reference ที่ไม่มี
suffix หรือ secret ที่ว่างจะทำให้ configuration fail fast. การตั้งค่า registry
ด้วยตัวเองควรส่ง `evm_secret_resolver` ที่เชื่อมกับ secret manager แทน fallback นี้.

## Offline preflight และ paper-only drill

ตรวจ registry และ adapter path โดยไม่ใช้ network หรือ credential จริงได้ด้วย:

```bash
cd strategy
.venv/bin/python scripts/evm_provider_preflight.py \
  --registry-file /path/to/evm-provider-registry.json \
  --json
```

คำสั่งนี้ใช้ `httpx.MockTransport` กับ fixture response, ตรวจ provenance และ
รัน risk gate ทุก chain ที่ระบุ (ค่าเริ่มต้นคือ EVM chains ทั้งหมด). ผลลัพธ์จะ
รายงาน `network_calls=false`, `credentials_loaded=false`,
`transactions_submitted=false` และ `production_activation=blocked` เสมอ.
ใช้ `--evidence-output` เพื่อเขียนเฉพาะ summary ที่ redacted และใช้
`--require-release-gate` เป็น check แยกเมื่อจะตรวจ approval record; คำสั่งนี้
ไม่เปิด endpoint จริงและไม่แทน provider dry-run ที่ต้องใช้ upstream sandbox
หลัง secret binding ผ่านการอนุมัติ

`status=passed` หมายถึงการตรวจด้วย fixture สำเร็จเท่านั้น ไม่ยืนยันความพร้อมของ
upstream หรือความปลอดภัยของเหรียญจริง. Registry ที่ `enabled=false` จะไม่เรียก
แม้แต่ mock endpoint และรายงาน `providers_exercised=false`; หลักฐานที่ขาดยังทำให้
risk gate เป็น `insufficient_evidence`. หากตรวจ redaction ไม่ผ่านจะรายงาน
`status=failed`. เมื่อใช้ `--require-release-gate` แต่ไม่มี approval ทั้ง stdout
และไฟล์ evidence จะรายงาน `status=blocked` พร้อม exit code 2.

## Acceptance checks ก่อนเปิด live endpoint

ทุก endpoint ต้องผ่าน checks เหล่านี้ใน environment ที่ไม่มี credential จริง:

1. ใช้ `httpx.MockTransport` ทดสอบ `408/425/429/5xx`, timeout และ transport
   error; retry ต้องหยุดภายใน `EVMRetryPolicy` และไม่ retry `4xx` ที่ไม่ transient
2. ส่ง header/secret ที่มี `CR/LF`, RPC block number หรือ logs shape ผิดรูปแบบ
   และ URL/query ที่มี credential; configuration หรือ scan ต้อง fail closed
3. ตรวจว่า provenance ไม่มี query string, header, body, raw secret หรือ exception
   message และ response hash เปลี่ยนเมื่อ source bytes เปลี่ยน
4. บังคับ required-provider failure ให้ได้ `provider_availability` และ
   `insufficient_evidence`; ห้ามให้ provider อื่นชดเชยเป็น `watchlist`
5. ส่ง payload ที่ invalid, stale, ขัดแย้งกัน, chain ไม่รองรับ และ token address
   ผิดรูปแบบ; ทุกกรณีต้อง fail closed หรือ `unsupported`
6. จำลอง sell หลายขนาด หลาย wallet และหลาย route ที่ read-only; แยก
   `success`, `failed` และ `inconclusive` และเก็บ block/route/amount/gas/tax
7. ตรวจ LP custody, unlock/expiry, emergency withdrawal และ concentrated
   liquidity; LP lock อย่างเดียวห้ามผ่านเป็นหลักฐานขายได้
8. รัน candidate cap, quota budget และ cancellation drill; endpoint ช้า/ล่ม
   ต้องหยุดการ enrich โดยไม่หยุด scanner ทั้งระบบ และต้องไม่ส่ง transaction
9. ตรวจ replay จาก provenance/manifest เดิมแล้วได้ผล schema/policy version เดิม
   และมี owner รับผิดชอบการเปลี่ยน adapter
10. ตั้ง `independence_group` ตาม upstream จริงและทดสอบว่า endpoint หลายชื่อจาก
    group เดียวกันไม่เพิ่ม independent evidence; group เดียวต้องยัง abstain

คำสั่งตรวจขั้นต่ำใน checkout นี้:

```bash
cd strategy
.venv/bin/pytest -q tests/test_evm_provider.py tests/test_evm_security.py tests/test_risk_gate.py
.venv/bin/ruff check app/market_intel/evm_provider.py app/market_intel/evm_security.py app/market_intel/risk_gate.py tests/test_evm_provider.py
```

## Go-live decision

เปิด endpoint ได้เมื่อ registry, secret binding, quota, owner, test evidence
และ incident/rollback record ครบทุกช่อง และ `required` ถูกตั้งตามหลักฐานที่
จำเป็นจริงของ chain/protocol นั้นเท่านั้น. การผ่าน gate หมายถึงระบบอ่านและ
reconcile หลักฐานได้ตาม policy version ณ เวลาตรวจ ไม่ใช่คำรับรองว่า token จะไม่
ถูก rug ในอนาคต

ก่อนเปิดให้ production เริ่มจาก candidate cap ต่ำและ paper-only watchlist.
หาก provider ใด stale, ขัดแย้ง, ถูก rate-limit, เปลี่ยน schema หรือมี chain
reorg ให้คง raw/provenance ไว้เพื่อ replay แล้วปิด endpoint นั้นทันที; ห้าม
แปลง unknown เป็น low risk และห้าม fallback ไปหา endpoint ที่ไม่ได้ review.

## Rollback และ approval record

Rollback คือถอด endpoint จาก injected registry, ปิด enrichment และคง raw
manifest/provenance สำหรับ replay. ไม่มีการ sign, approve หรือส่งธุรกรรมใน
ขั้นตอน rollback.

| Role | Name/date | Decision/evidence |
|---|---|---|
| Market-intelligence owner |  |  |
| Data/provider owner |  |  |
| Security/operations owner |  |  |
| Risk-policy reviewer |  |  |
