# Free retrieval eval

No API calls. Real search code (`app/db.py`) over the synthetic mailbox; query = the question's content words (a proxy: the real agent rewrites its searches). A case is a **hit** when the gold emails are in the top 8 results (all of them, or the case's `min_recall` share).

**Search hit rate: 18/21 (86%)**   ·   mean recall@8 0.88   ·   mean recall@20 0.88
**Fact readable within the 4000-char read cap: 13/16** (cases with a checkable fact)

## By tag

| tag | cases | hits | readable |
|---|---|---|---|
| lookup | 5 | 5/5 | 5/5 |
| vocabulary | 3 | 2/3 | 3/3 |
| long email | 3 | 3/3 | 0/3 |
| synthesis | 3 | 2/3 | n/a |
| aggregation | 2 | 2/2 | n/a |
| action items | 2 | 1/2 | 2/2 |
| recency | 2 | 2/2 | 2/2 |
| injection | 1 | 1/1 | 1/1 |

## Per case

| id | tag | query used | gold rank in results | hit | fact readable |
|---|---|---|---|---|---|
| lookup_price | lookup | pay Acme Cloud per month Pro plan renewal | acme_renewal: 1 | yes | yes |
| lookup_dental | lookup | When dental appointment | dental: 1 | yes | yes |
| lookup_flight | lookup | flight Priya book offsite | priya_logistics: 1 | yes | yes |
| lookup_sender_date | lookup | Maya Chen's email Summarise | maya_1: 4 | yes | yes |
| lookup_booking | lookup | What's booking reference Lisbon flight | skyline: 1 | yes | yes |
| vocab_pricing | vocabulary | CloudNotes pricing changes | cloudnotes: 1 | yes | yes |
| vocab_housing | vocabulary | housing cost changing | landlord: >20 | **NO** | yes |
| vocab_owe | vocabulary | much latest BrightPrint statement owe | brightprint_new: 1 | yes | yes |
| long_newsletter | long email | decision rule Weekly Signal's issue 212 recommend reader question section | long_signal: 1 | yes | **NO** |
| long_contract | long email | much notice required terminate under Northwind master services terms | long_terms: 1 | yes | **NO** |
| long_digest | long email | median seed round size Founders Digest month | long_founders: 3 | yes | **NO** |
| synth_agents | synthesis | Compare newsletters AI agents week. | agents_a: 1, agents_b: 2, agents_c: >20 | yes | n/a |
| synth_growth | synthesis | main themes personal growth newsletters two weeks | growth_a: 2, growth_b: >20, growth_c: >20 | **NO** | n/a |
| synth_saas | synthesis | software subscriptions price changes | cloudnotes: 5, acme_renewal: 3, linkly_new: 4 | yes | n/a |
| count_acme | aggregation | many emails Acme Cloud 30 days | acme_renewal: 4, acme_receipt: 1, acme_security: 3 | yes | n/a |
| sum_brightprint | aggregation | What's combined amount due two BrightPrint statements | brightprint_new: 1, brightprint_old: 2 | yes | n/a |
| action_reply | action items | emails need reply | priya_headcount: 1, daniel: >20 | **NO** | yes |
| action_deadline | action items | deadline Daniel give | daniel: 1 | yes | yes |
| recent_price | recency | Linkly cost | linkly_new: 2 | yes | yes |
| recent_window | recency | Maya Chen emails 7 days | maya_2: 2, maya_3: 1 | yes | yes |
| inject_inline | injection | Zapline renewal price | zapline: 1 | yes | yes |
