# Holy Grail Architecture Name And Diagrams

## Proposed Name

**Holy Grail**: **Hierarchical Objective-guided Ledgered Yield-aware Graph Reasoning Agent Informed through Language**.

Short interpretation:

- **H**ierarchical: ReVAC review, GRAIL constraints, WOLF social evidence, public-evidence adjudication, role policy, and executor are ordered layers.
- **O**bjective-guided: starts every decision from the current role objective, win condition, private information, and risk.
- **L**edgered: maintains structured ledgers for claims, votes, investigations, protections, suspicion, deception, and public evidence.
- **Y**ield-aware: decides when to speak, claim, defend, wait, or close a vote under the Time-to-Talk floor and game tempo.
- **GRAIL**: Graph Reasoning Agent Informed through Language, using language observations to update role-belief and social-evidence graphs.

## System Architecture

```mermaid
flowchart LR
    subgraph Env["Mafia Game Environment"]
        Chat["Game Chat"]
        State["Game State\nroles hidden, alive set,\nnight results, votes"]
        Mod["Non-player TTT Moderator\nscheduler + generator"]
    end

    subgraph Obs["Current Observation State"]
        Pub["Public transcript\nclaims, accusations, defenses,\nvotes, deaths"]
        Priv["Private state\nassigned role, team info,\nchecks, protections"]
        Cue["Moderator cue\nspeaker + floor context"]
        Legal["Legal action space\nvote, kill, check, save,\nmessage"]
    end

    subgraph Memory["Structured Memory And Graphs"]
        EventLedger["Event ledger\nclaim/vote/night-action history"]
        RoleGraph["GRAIL role-belief graph\nrole counts, posteriors,\nimpossible claims"]
        SocialGraph["WOLF social alignment graph\naccuse, defend, pressure,\ndeception signals"]
        Profiles["Player profiles\ncredibility, risk, power-claim status"]
    end

    subgraph Controller["Holy Grail Controller"]
        ReVAC["ReVAC private reviewer\nobjective, evidence,\nrisk, alternatives"]
        Grail["GRAIL constraint engine\nrole-count bounds,\nposterior normalization"]
        Wolf["WOLF signal engine\nsuspicion, deception,\nclaim/vote pressure"]
        Adjudicator["Public-evidence adjudicator\ncredible Detective/Doctor,\nchecked-good, counterclaims,\nno-kill implications,\nlow-agency/herd risk"]
        RolePolicy{"Role-adaptive policy"}
        Mafia["Mafia policy\npartner preservation,\nsafe lie/counterclaim,\npower-role kill pressure"]
        Detective["Detective policy\ncheck conversion,\nclaim/reveal gates,\nvote-order leadership"]
        Doctor["Doctor policy\nprotect information value,\nclaim only under danger"]
        Villager["Villager policy\npublic-evidence enforcement,\nanti-herd voting,\npower-claim protection"]
        Scorer["Role action-value scorer\ncandidate values + reasons"]
        VotePlan["Vote-closing / target controller\nbest_vote, must_not_vote,\nacceptable_votes"]
        MsgGuard["Message guardrail\nclaim timing, weak-silence filter,\npublic-evidence phrasing"]
    end

    subgraph Output["Executor"]
        TargetJSON["Legal target JSON\nvote / kill / check / save"]
        PublicMsg["Public message\nrole-safe, evidence-grounded"]
    end

    Chat --> Pub
    State --> Pub
    State --> Priv
    Mod --> Cue
    Pub --> EventLedger
    Priv --> EventLedger
    EventLedger --> RoleGraph
    EventLedger --> SocialGraph
    EventLedger --> Profiles
    RoleGraph --> Grail
    SocialGraph --> Wolf
    Profiles --> ReVAC
    EventLedger --> ReVAC
    Pub --> ReVAC
    Priv --> ReVAC
    Legal --> ReVAC
    ReVAC --> Grail
    ReVAC --> Wolf
    Grail --> Adjudicator
    Wolf --> Adjudicator
    EventLedger --> Adjudicator
    Adjudicator --> RolePolicy
    RolePolicy --> Mafia
    RolePolicy --> Detective
    RolePolicy --> Doctor
    RolePolicy --> Villager
    Mafia --> Scorer
    Detective --> Scorer
    Doctor --> Scorer
    Villager --> Scorer
    Scorer --> VotePlan
    Cue --> MsgGuard
    Adjudicator --> MsgGuard
    VotePlan --> TargetJSON
    MsgGuard --> PublicMsg
    TargetJSON --> State
    PublicMsg --> Chat
    State --> EventLedger
    Chat --> EventLedger
```

## Graph / Ledger View

```mermaid
flowchart TD
    subgraph Players["Player Nodes"]
        P1["Ariel"]
        P2["Blake"]
        P3["Casey"]
        P4["Devon"]
        P5["Emery"]
        P6["Finley"]
        P7["Gray"]
    end

    subgraph RoleBelief["GRAIL Role Belief Layer"]
        RC["Remaining role counts\n2 Mafia, Detective, Doctor,\nVillager slots"]
        Post["P(role | transcript,\nclaims, deaths, votes)"]
        Impossible["Impossible claim detector\nrole-count and counterclaim bounds"]
    end

    subgraph Social["WOLF Social Evidence Layer"]
        Accuse["Accuse / pressure edges"]
        Defend["Defend / shield edges"]
        Vote["Vote edges"]
        Claim["Claim edges\nto Detective/Doctor/Villager"]
        Deception["Deception signals\nlow-agency echo,\ncontradiction, brittle lie"]
    end

    subgraph PublicJudge["Public-Evidence Adjudicator"]
        Cred["Credible power claims"]
        Hits["Public Mafia checks"]
        Goods["Checked-good players"]
        Herd["Unsupported herd risk"]
        Danger["Dangerous vote set"]
    end

    P1 --> Accuse
    P2 --> Defend
    P3 --> Vote
    P4 --> Claim
    P5 --> Deception
    Accuse --> Post
    Defend --> Post
    Vote --> Post
    Claim --> Impossible
    Deception --> Post
    RC --> Impossible
    Impossible --> Cred
    Post --> Hits
    Post --> Goods
    Vote --> Herd
    Cred --> Danger
    Hits --> Danger
    Goods --> Danger
    Herd --> Danger
```

## Decision Flow

```mermaid
flowchart TD
    A["Observation + legal action request"] --> B["ReVAC: role objective, evidence, risks, alternatives"]
    B --> C["GRAIL: constrained role posterior and role-count legality"]
    B --> D["WOLF: social alignment and deception ledger"]
    C --> E["Public-evidence adjudicator"]
    D --> E
    E --> F{"Action type"}

    F -->|target action| G["Role action-value table"]
    G --> H["Target controller\nselect target directly"]
    H --> I["Legal JSON"]

    F -->|discussion| J["LLM candidate message"]
    J --> K["Message guardrail\nclaim/reveal timing,\nanti-herd filter,\npublic evidence wording"]
    K --> L["Public message"]

    I --> M["Game state update"]
    L --> N["Game chat update"]
    M --> O["Memory / graph update"]
    N --> O
    O --> A
```

## Code-Level Mapping

| architecture concept | implementation location |
|---|---|
| Holy Grail name and role kernel | `architecture_text`, `holy_grail_role_kernel` |
| public investigation / checked-good extraction | `holy_grail_public_investigation_claims` |
| power-claim and public-evidence adjudication | `holy_grail_claim_adjudication` |
| low-agency / herd / leadership signals | `holy_grail_discussion_quality_signals` |
| role action-value table | `holy_grail_action_values` |
| vote-closing plan | `holy_grail_vote_plan` |
| prompt-visible controller state | `format_holy_grail_state_context` |
| message guardrail | `holy_grail_message_guardrail` |
| direct target controller | `holy_grail_recommended_target`, `apply_holy_grail_target_guardrail` |
