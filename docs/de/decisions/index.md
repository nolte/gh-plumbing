# Entscheidungen

Architecture Decision Records für Entscheidungen, die über dieses Repository
hinaus wirken.

`gh-plumbing` ist eine reine Konfigurationsbibliothek. Ihre wiederverwendbaren
Workflows und Probot-Commons laufen in jedem Consumer-Repository, eine
Entscheidung hier verändert also fremde CI ohne deren Zutun. Diese Aufzeichnungen
gibt es, damit ein Consumer das Warum findet, ohne einen geschlossenen
Issue-Thread zu lesen.

Entscheidungen, die nur dieses Repository betreffen, bleiben in ihrem Issue. Hier
landet, was verändert, was Consumer erben.

| Record | Thema | Status |
|---|---|---|
| [ADR-001](adr-001-presentation-branch-reset.md) | Präsentationsbranch auf den Release-Tag zurücksetzen | Angenommen |
| [ADR-002](adr-002-branch-protection-verification.md) | Branch Protection prüfen, bevor die Defaults geändert werden | Angenommen |
| [ADR-003](adr-003-workflow-validation-gate.md) | Workflow-Gültigkeit über einen Required Check absichern | Angenommen |
| [ADR-004](adr-004-spec-drift-routing.md) | Den Q2-Spec-Drift-Cluster über die Roadmap führen | Angenommen |

## Format

Jede Aufzeichnung nennt den Kontext, die Entscheidung, die unterlegenen
Alternativen und die Folgen, mit denen ein Consumer rechnen sollte. Das jeweils
verlinkte GitHub-Issue trägt die Akzeptanzkriterien und die Umsetzungsspur.
