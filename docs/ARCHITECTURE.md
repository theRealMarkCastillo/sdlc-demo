# Architecture

The SDLC pipeline that built this demo project. Built on [Hermes Agent](https://hermes-agent.nousresearch.com/) profiles + subagents, modeled on Anthropic's three-article pattern ([security](https://claude.com/blog/how-anthropic-secures-its-ai-native-software-development-lifecycle), [identity](https://claude.com/blog/agent-identity-access-model), [migration](https://claude.com/blog/ai-code-migration)).

## The 8-Node Cycle

The SDLC is a cycle, not a pipeline. Monitor feeds back to Ideation. Governance is cross-cutting, not a stage.

```mermaid
flowchart TB
    Human([Human Initiator]) --> Idea[Ideation]
    Idea --> Plan[Plan]
    Plan --> Code[Code]
    Code --> Review[Test/CI<br/>3-reviewer AND-gate]
    Review -->|All PASS| Deploy[Deploy<br/>Human gate P0/P1]
    Review -->|Any FAIL| Code
    Deploy --> Done[Done]
    Done --> Monitor

    Monitor[Monitor<br/>sdlc-monitor cron profile] -.->|critical anomaly| NewCard([New card<br/>on kanban board])
    NewCard -.-> Idea

    Gov[/Governance<br/>cross-cutting/] -.-> Plan
    Gov -.-> Code
    Gov -.-> Review
    Gov -.-> Deploy
    Gov -.-> Done
    Gov -.-> Monitor

    style Gov fill:#f9f,stroke:#333
    style NewCard fill:#fee,stroke:#c33
    style Review fill:#eef,stroke:#333
    style Deploy fill:#efe,stroke:#333
```

## What Runs When

The cycle is real but the rates differ. Here's how often each node fires in this demo:

| Node | Trigger | Frequency | Latency |
|------|---------|-----------|---------|
| Ideation | Human or monitor | Ad-hoc | n/a |
| Plan | Orchestrator | Per P0/P1 card | <2s |
| Code | Worker subagent | Per card | 30s–2min |
| Test/CI | Orchestrator | Per card | 1–2min (3 reviewers in parallel) |
| Deploy | Orchestrator | Per card | 30s (Docker rebuild) + human reply wait |
| Done | Orchestrator | Per card | <1s |
| Monitor | Cron | Every 15 min | <5s |
| Governance | Cron | Daily 8 AM | <30s |

## One Card, End-to-End

Sequence of a typical P1 card from creation to deployment.

```mermaid
sequenceDiagram
    actor Mark
    participant Orch as Orchestrator<br/>(Arx)
    participant KB as Kanban Board
    participant SE as Worker<br/>(software-engineer)
    participant Rev as Reviewers<br/>(3x parallel)
    participant TB as Tiebreaker
    participant Dep as Deploy Worker
    participant TG as Telegram
    participant Repo as ~/git/sdlc-demo

    Mark->>Orch: "/sdlc add password reset endpoint"
    Orch->>KB: kanban_create("SDLC-005: ...")
    Orch->>SE: delegate_task(goal, context, AGENTS.md)
    SE->>Repo: TDD: tests RED → GREEN
    SE->>Orch: "5/5 tests, commit abc123"
    Orch->>KB: status → Test/CI
    par Parallel reviewers
        Orch->>Rev: security review
        Orch->>Rev: spec review
        Orch->>Rev: quality review
    end
    Rev-->>Orch: 3 verdicts

    alt All PASS
        Orch->>Dep: deploy worker
        Dep->>Repo: docker compose staging up
        Dep->>TG: "approve SDLC-005 abc123 production?"
        Mark->>TG: "approve SDLC-005 abc123 production"
        TG->>Dep: approval validated
        Dep->>Repo: docker compose prod up
    else Any FAIL
        Orch->>TB: resolve dispute (cite DoD)
        TB-->>Orch: verdict + reasoning
        alt Verdict = REVIEWER_CORRECT
            Orch->>SE: retry (max 3)
        else Verdict = QUALITY_CORRECT
            Orch->>Dep: proceed
            Dep->>TG: approval request
        end
    end

    Orch->>KB: status → Done
    Orch->>Repo: governance.py (daily metrics)
```

## Identity Scopes

Three scopes from Anthropic's agent identity blog, mapped to Hermes profiles:

```mermaid
flowchart LR
    subgraph Workspace["Workspace Scope"]
        W1[default profile<br/>Full toolset<br/>Personal access]
        W2[sdlc-monitor profile<br/>file, kanban, web<br/>Workspace credentials]
    end

    subgraph PrivateChannel["Private Channel Scope"]
        PC[Per-dispatch subagent<br/>Isolated context<br/>Auto-revoked]
    end

    subgraph PersonalDM["Personal DM Scope"]
        PDM[Local terminal<br/>No agent context<br/>Single user]
    end

    Workspace -->|orchestrator dispatches| PrivateChannel
    Workspace -->|human reviews| PersonalDM
    PrivateChannel -.->|kill switch| Revoked([Revoked<br/>context destroyed])
```

**Revocability:** Deleting `~/.hermes/profiles/sdlc-monitor/` ends its access. Subagent contexts die when the parent session ends. Personal DM is a person, not a credential.

## Storage Map

Where each piece of state lives. Boundary discipline matters.

```mermaid
flowchart TB
    subgraph HermesKanban["Hermes Kanban (canonical board)"]
        KB[Board: sdlc<br/>All card state<br/>Comments, events]
    end

    subgraph HermesSkills["~/.hermes/skills/"]
        S1[sdlc]
        S2[sdlc-orchestration]
        S3[sdlc-security-review]
        S4[sdlc-tiebreaker]
        S5[sdlc-deploy]
        S6[sdlc-monitor]
        S7[sdlc-governance]
    end

    subgraph HermesProfile["~/.hermes/profiles/sdlc-monitor/"]
        P1[config.yaml<br/>toolsets: file, kanban, web]
        P2[SOUL.md<br/>3 permissions]
        P3[.env<br/>API keys]
    end

    subgraph HermesScripts["~/.hermes/scripts/"]
        SC1[sdlc-log-scan.py<br/>Invoked by cron]
    end

    subgraph ProjectRepo["~/git/sdlc-demo/ (project)"]
        PR1[app.py, tests/, compose]
        PR2[README.md, docs/]
        PR3[AGENTS.md<br/>closed-loop rules]
    end

    subgraph Wiki["~/wiki/ (companions only)"]
        W1[NO SDLC CONTENT]
    end

    HermesKanban <--> HermesSkills
    HermesSkills --> ProjectRepo
    HermesProfile --> HermesScripts
    HermesScripts -->|docker logs| ProjectRepo
    ProjectRepo -.->|excluded| Wiki

    style Wiki fill:#fee,stroke:#c33
```

## Multi-Reviewer AND-Gate Detail

Three reviewers run in parallel with isolated contexts. All three must PASS for the card to advance. Adversarial mindset.

```mermaid
stateDiagram-v2
    [*] --> CodeSubmitted
    CodeSubmitted --> Reviewing
    Reviewing --> Security
    Reviewing --> Spec
    Reviewing --> Quality

    Security --> Verdict1
    Spec --> Verdict2
    Quality --> Verdict3

    state Verdict1 <<choice>>
    state Verdict2 <<choice>>
    state Verdict3 <<choice>>

    Verdict1 --> Aggregate: PASS / FAIL
    Verdict2 --> Aggregate: PASS / FAIL
    Verdict3 --> Aggregate: PASS / FAIL

    Aggregate --> Deploy: all PASS
    Aggregate --> Tiebreaker: any disagreement
    Aggregate --> Retry: any FAIL (max 3)

    Tiebreaker --> Deploy: tiebreaker = REVIEWER_CORRECT → retry
    Tiebreaker --> Deploy: tiebreaker = QUALITY_CORRECT → proceed

    Retry --> CodeSubmitted
    Deploy --> Done
```

## Closed Loop

When a reviewer catches a recurring pattern, the orchestrator edits the rulebook — not the code. Future workers read the updated instructions on first dispatch.

```mermaid
flowchart LR
    A[Worker dispatches<br/>reads AGENTS.md] --> B[Code generated]
    B --> C[Reviewer catches<br/>recurring pattern]
    C --> D[Pattern = bug class<br/>e.g., type-coercion]
    D --> E[Orchestrator edits<br/>AGENTS.md or skill]
    E --> F[Commit + push]
    F --> G[Next worker reads<br/>updated rule]
    G --> A

    style E fill:#efe,stroke:#393
```

**Example:** SDLC-001 reviewers caught `bool-as-age` and missing-email-type-guard holes. Orchestrator appended two lines to the project's `AGENTS.md` under "Security Rules". SDLC-002's worker read them first and never repeated the bug class.

## More Reading

- [INCIDENT-RESPONSE.md](INCIDENT-RESPONSE.md) — what happens when the monitor catches a production issue
- [REVIEW-PROCESS.md](REVIEW-PROCESS.md) — deeper on the multi-reviewer pattern and tiebreaker
- [DEPLOYMENT.md](DEPLOYMENT.md) — staging vs prod infrastructure
- [API.md](API.md) — endpoints and request/response shapes
- [SDLC-SYSTEM.md](SDLC-SYSTEM.md) — concise integration guide for the SDLC system