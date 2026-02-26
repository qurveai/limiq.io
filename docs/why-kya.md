# Why KYA

AI agents can now trigger real-world actions: purchases, CRM writes, deployments.

The core risk is simple:
- an agent acts with too much power,
- or outside policy,
- and you only discover it after damage is done.

## The concrete risk
Without a control gate, one bad call can:
- execute an unauthorized purchase,
- push wrong data to your CRM,
- trigger an unsafe deploy.

## The KYA verify gate
KYA adds one decision point before execution:

`verify -> ALLOW or DENY`

Your app executes only on `ALLOW`.
On `DENY`, you get a reason code you can log and handle.

## What this gives you
- Identity: which agent is acting
- Permission control: what it can do now
- Audit trail: what happened and why
- Revocation: stop an agent or capability immediately

KYA is the trust layer between agent intent and production action.
