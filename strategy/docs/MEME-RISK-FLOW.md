# Meme discovery and risk flow

สถานะ: bounded implementation — discovery/risk gate, EVM schema adapter และ
secret-free provider registry อยู่ใน market-intel contract แล้ว; runtime secret
binding, live simulation และ historical validation ยังไม่ครบทุก chain
วันที่ตรวจ: 2026-09-08
ขอบเขตเจ้าของ: BookFinance / booktrading market intelligence
ผู้ใช้ผลลัพธ์: research watchlist และ paper evaluation

## ผลลัพธ์ที่ต้องการ

ค้นหาเหรียญที่มีเหตุผลให้ติดตาม พร้อมหลักฐานความเสี่ยงและความสามารถในการขายออก
ไม่แสดงคำว่า safe หรือโอกาสไม่ rug เป็นเปอร์เซ็นต์ที่ยังไม่ผ่านการประเมินย้อนหลัง
การไม่พบธงแดงไม่ใช่หลักฐานว่าปลอดภัยในอนาคต

## สิ่งที่ implement แล้วในรอบนี้

- `strategy/app/market_intel/risk_gate.py` มี typed `RiskEvidence`,
  `RiskDecision` และ deterministic hard-veto policy
- `DegenSource` ตรวจทุก chain ใน `TARGET_CHAINS`, รวม evidence ตอน deduplicate
  และไม่ส่ง quote ที่ไม่ผ่าน gate เข้า opportunity ranking
- Solana event เก็บ `decoder_status` แยกจาก log hint และแนบ risk decision;
  log ที่ยืนยัน program instruction ไม่ได้จะคงไว้เพื่อ replay แต่ไม่ผ่าน gate
- DexScreener boost ถูกเก็บเป็น paid discovery signal เท่านั้น ไม่ใช่ risk evidence
- `market_intel/evm_security.py` แปลง payload ที่ fetch มาแล้วจาก GoPlus,
  Honeypot และ read-only sell simulation/LP custody ให้เป็น schema กลาง
  `evm-security.v1`; adapter ไม่เรียก network และไม่ส่ง transaction
- การรวม observation เก็บ provider conflict, sell status, tax/proxy findings,
  LP lock ratio/expiry และ custody verification ไว้ให้ gate abstain เมื่อ reconcile ไม่ได้
  (EVM adapter ต้องมี custody proof ชัดเจนก่อนจึงจะครบหลักฐาน)
- registry รองรับ `independence_group` เพื่อไม่นับ API หลายชื่อจาก upstream เดียวกัน
  เป็นหลักฐานอิสระหลายชุด
- gate ต้องเห็น independent provider อย่างน้อยสองกลุ่มก่อน `watchlist` หรือ
  `paper_candidate`; แหล่งเดียวหรือ group เดียวจะเป็น `insufficient_evidence`
- `market_intel/evm_provider.py` มี outer boundary แบบ opt-in สำหรับ endpoint ที่
  caller กำหนดเอง: retry เฉพาะ transient failure, จำกัด backoff, เก็บ provenance
  แบบไม่ติด secret และส่ง required-provider failure เข้า gate เป็น evidence ที่ไม่ครบ
- `docs/EVM-PROVIDER-RELEASE-GATE.md` กำหนด registry, secret binding, quota,
  simulation, replay และ rollback evidence ก่อนเปิด endpoint จริง
- `EVMProviderRegistry` ตรวจ version/endpoint/chain coverage, บังคับ release
  approval ก่อน materialize endpoint และรับ secret ผ่าน resolver ใน memory เท่านั้น
- `MarketScanner` รับ `evm_provider_registry` หรือ `evm_provider_ingestor` แบบ
  explicit แล้วส่งต่อให้ `DegenSource`; จึงไม่เกิด live provider call จากการ
  import หรือจาก scanner ค่าเริ่มต้น. ถ้าส่ง registry ที่เปิดใช้แต่ไม่ผ่าน
  release gate จะ fail-fast ก่อนเริ่ม scan
- มี tests สำหรับ missing/stale/conflicting evidence, honeypot/sell failure,
  Solana authority, holder/LP concentration และ unsupported chain

## Coverage ตามหลักฐานปัจจุบัน

- Solana: มี RPC/WebSocket discovery แบบ opt-in, การตีความ log และ risk enrichment เบื้องต้น
- EVM: มี `EVMOnchainSource` แบบ opt-in สำหรับ `eth_getLogs` ของ factory/pair
  event ที่กำหนดเองต่อ chain; เป็น discovery event เท่านั้นและไม่มี default
  RPC/factory ที่เปิดใช้งานเอง
- DexScreener: TARGET_CHAINS มี solana/bsc/ethereum/base/arbitrum และ loop ค้นรายเชนทำครบทุก chain
- Birdeye: enrichment เฉพาะ Solana แบบ optional
- EVM protocol-specific decoders ที่ยืนยัน ABI หลายรูปแบบ และ non-EVM families
  อื่นยังต้องพัฒนา
- Compaction, restore และ bucket checks เป็น infrastructure; ไม่ใช่หลักฐานว่า token ปลอดภัย

ต้องมี registry ราย chain + protocol + version แสดง discovery, decoder, security,
simulation, finality และ freshness เป็น supported/partial/unsupported
เชนหรือ protocol ที่ไม่มี decoder ต้องเป็น unsupported ไม่ผ่านเป็น low risk โดยปริยาย

## Pipeline ที่เสนอ

1. Discover: ฟัง token/pool creation และ launchpad migration จาก RPC/WS ของ protocol ที่รู้จัก
   ใช้ indexer, market data และ social เป็นแหล่งเสริม ระบุ paid promotion ชัดเจน
2. Land: เก็บ exact source bytes, checksum และ Bronze manifest ก่อนส่งต่อ
   ต้องครอบคลุม backfill และ transaction enrichment ด้วย ไม่ใช่เฉพาะ live logs
3. Identify: chain namespace + chain ID + token address + pool address
   เก็บ block hash/slot, transaction hash, log/instruction index และ decoder version
   ตรวจ instruction/event กับ program/factory จริง ไม่ใช้ข้อความ log หรือ ticker เพียงอย่างเดียว
4. Verify: ตรวจสิทธิ์แก้สัญญา/เพิ่ม supply/แช่แข็ง/ย้ายเหรียญ/เปลี่ยนภาษี/ระงับการขาย
   ตรวจ pool reserves, quote asset, LP custody/lock/unlock และตำแหน่ง concentrated liquidity
5. Simulate: ทดสอบ buy→sell ใน simulation หลายขนาด หลาย wallet และหลาย route
   บันทึก block, route, amount, gas, tax, price impact และ failure reason
   ไม่ส่ง transaction จริง และไม่ถือว่า simulation success รับประกันการขายในอนาคต
6. Analyze: deployer history, funding links, holder clusters, bundled/sniper activity,
   liquidity flows, organic unique buyers/sellers และปริมาณซื้อขายที่น่าสงสัย
7. Decide: hard veto มาก่อน ranking; unknown/stale/conflicting evidence ห้ามแปลงเป็น pass
8. Monitor: เปลี่ยนสถานะเมื่อ authority, implementation, tax, liquidity หรือ finality เปลี่ยน
   ยกเลิกผลเก่าเมื่อ reorg หรือข้อมูลหมดอายุ และประเมินใหม่ก่อน paper consideration

## States

| State | ความหมาย |
|---|---|
| detected | พบ event แต่ยังตรวจไม่ครบ |
| unsupported | chain/protocol/version ยังตรวจไม่ได้ |
| insufficient_evidence | ข้อมูลขาด, stale, RPC ล่ม หรือ simulation สรุปไม่ได้ |
| high_risk | พบความสามารถอันตรายหรือ exit risk ตาม policy; ไม่ใช่ข้อกล่าวหาว่าผู้สร้างโกง |
| watchlist | หลักฐานจำเป็นครบและยังไม่พบ veto ณ block ที่ตรวจ |
| paper_candidate | ผ่าน watchlist และมี demand/executable depth ที่ควรทดลองใน paper |
| invalidated | หลักฐานเดิมใช้ไม่ได้จากการเปลี่ยน state หรือ reorg |

รายงานแยก risk findings, evidence coverage/freshness และ opportunity features
ห้าม momentum/paid boost ชดเชย honeypot หรือ missing critical evidence

## Chain-specific controls

| Family | ต้องตรวจเพิ่ม |
|---|---|
| EVM | proxy implementation/admin, hidden roles, mint, blacklist, pause, mutable taxes, max wallet/tx, external calls, factory/router authenticity, LP token/NFT custody |
| Solana | mint/freeze authority, Token-2022 permanent delegate, transfer hooks/fees, default frozen/pausable state, custom program upgrade authority, vault owner และ launchpad migration |
| Move/อื่น ๆ | package upgrade, mint/admin capabilities, denylist/pause และ DEX custody ตาม native model; ต้องมี adapter เฉพาะก่อนรับรอง coverage |

## Edge cases และเกณฑ์ตรวจรับ

| กรณี | พฤติกรรมที่ต้องได้ |
|---|---|
| RPC timeout/429, indexer ช้า | unknown + retry/backoff; ห้าม low risk |
| ราคาหรือ contract data ต่าง block | เก็บทั้ง observation; reconcile ก่อนจัดอันดับ |
| สอง API ใช้ upstream เดียวกัน | นับ independence ตาม upstream ไม่ใช่จำนวนโลโก้ |
| ซื้อได้ แต่ sell revert | high_risk ถ้าพิสูจน์ข้อจำกัดได้; simulation error ทั่วไปเป็น inconclusive |
| ขายขนาดเล็กได้แต่ขนาดจริงไม่ได้ | ประเมินตาม amount/route; ไม่มี universal sellable flag |
| honeypot เปิดภายหลัง/whitelist เฉพาะ wallet | ตรวจหลาย state/wallet และติดตาม authority; pass มีอายุจำกัด |
| renounced owner แต่ proxy/role ยังแก้ได้ | ตรวจ effective authority graph; ห้ามผ่านจาก owner=zero |
| LP burn/lock แต่มี mint หรือ dump supply | ประเมิน supply/holder risk แยกจาก LP lock |
| lock บางส่วน/ใกล้หมด/locker มี emergency withdrawal | รายงานสัดส่วน สิทธิ์ถอนและเวลาปลดจริง |
| concentrated liquidity หลุด price range | ใช้ active executable depth ไม่ใช้ headline TVL |
| fake quote token หรือราคา USD ผิด | ตรวจ address ของ quote และแหล่งอ้างอิง; quarantine valuation |
| wash trades, Sybil holders, bundled wallets | แยก raw count กับ cluster-adjusted estimate และ confidence |
| top holders เป็น LP vault/bridge/CEX | ยกเว้นเมื่อมีหลักฐานประเภทบัญชี; unknown ห้ามเดา |
| wallet รับเงินจาก CEX เดียวกัน | ไม่ถือว่าเป็นเจ้าของเดียวกันจาก funding link อย่างเดียว |
| mint spoof, Unicode symbol, pool ปลอม | identity ตาม chain/address/factory และตรวจ decoder |
| migration, duplicate delivery, reconnect, reorg | idempotent event key; retract orphaned observations และ replay gap |
| arbitrary log ว่า Create | ต้องพิสูจน์ instruction/account ก่อนบอกว่า token created |
| token rebasing/fee-on-transfer/nonstandard decimals | adapter เฉพาะ; parse ผิดต้องหยุด ไม่คำนวณกำไรต่อ |
| bridge exploit, sequencer outage, MEV | แสดง chain/execution risk แยกจาก token risk |
| social website/phishing/airdrop approvals | แสดงข้อมูลเป็น untrusted content; ไม่มี auto-connect/sign/approve |

## Opportunity ranking และ validation

จัดอันดับเฉพาะตัวผ่าน evidence gate จาก demand ต่อเนื่อง, net liquidity inflow,
unique funded participants, effective concentration และ exit cost ตามขนาด paper position
แสดงอายุเหรียญและ liquidity denominator; volume/liquidity สูงอาจเป็น wash trading
ค่าตัดทั้งหมดเป็น policy version ที่ต้องทดลอง ไม่ใช่ค่ารับประกันกำไร

ประเมินย้อนหลังด้วย universe ที่รวมเหรียญตายและ rug ไม่เฉพาะ survivors
ใช้ข้อมูลที่มี ณ เวลาตัดสินใจ แบ่ง holdout ตามเวลาและ deployer cluster
วัด missed-rug rate, false-positive rate, abstention/coverage, detection delay,
drawdown และ paper P&L หลัง fee/slippage/MEV assumptions
จำแนก fraud, liquidity collapse และ price crash โดยไม่ใช้ราคาตกอย่างเดียวเป็น rug label

## ลำดับพัฒนา

1. เพิ่ม typed evidence/state contract และ veto policy ให้ scanner เดิม; แก้ paid-boost assumption
2. ทำ Solana instruction decoder + extension checks + simulation และ backfill lineage ให้ครบ
3. ผูก EVM schema-only adapter และ `EVMProviderIngestor` นี้กับ RPC/provider
   endpoint ทีละ chain/protocol พร้อม simulation cross-check, timeout/429 retry
   และ source manifest; live endpoint ต้องผ่าน
   [`EVM-PROVIDER-RELEASE-GATE.md`](EVM-PROVIDER-RELEASE-GATE.md)
4. เพิ่ม watchlist endpoint/UI แสดง reason, block, freshness, coverage และ exit estimates
5. ทำ continuous invalidation และ historical paper evaluation ก่อนขยาย chain coverage

Rollback: ปิด adapter ใหม่และคง raw/manifests สำหรับ replay; ไม่เปลี่ยน trading execution
Production acceptance ต้องมีหลักฐานราย adapter และ owner/consumer review ตาม release contract

## Primary references

- https://solana.com/docs/tokens/extensions
- https://solana.com/docs/tokens/extensions/permanent-delegate
- https://docs.gopluslabs.io/reference/response-details
- https://docs.gopluslabs.io/reference/tokensecurityusingget_1
- https://docs.honeypot.is/ishoneypot
