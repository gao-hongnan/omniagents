# Prior art: Claude Code skills/plugins for Terraform / IaC / Docker (as of 2026-07-20)
(research digest from web-research agent)

## Official Anthropic surfaces — no IaC skills

- anthropics/skills: 18 skills (docx/pdf/pptx/xlsx, frontend-design, mcp-builder, skill-creator...). Zero terraform/docker/devops entries.
- anthropics/claude-plugins-official: only IaC entry is external_plugins/terraform = a 2-file wrapper around HashiCorp's MCP server. No skill content. No docker plugin.
- Big awesome lists (ComposioHQ ★68k, travisvn ★14k): no DevOps/IaC/Terraform/Docker sections at all — only tangential SaaS automations and zxkane/aws-skills (CDK).

## Found skills/plugins

| Name / repo | ★ / updated | Coverage | Depth |
|---|---|---|---|
| antonbabenko/terraform-skill | 2.2k / v1.17.1 Jun 2026 | TF+OpenTofu: module hierarchy (resource/infra/composition), code patterns (count-vs-for_each, moved, write-only args), state mgmt, security/compliance (Trivy/Checkov), CI/CD, testing (native vs Terratest), terraform-ls. Diagnose-first workflow + response contract, failure-mode routing table. Multi-agent installs (Claude plugin via antonbabenko/agent-plugins, Cursor, Codex...) | DEEP: 20KB SKILL.md + 8 refs ≈175KB (state-management alone 46KB). By the terraform-aws-modules maintainer |
| hashicorp/agent-skills | 744 / Jul 15 2026 | Official HashiCorp marketplace: terraform-style-guide (7KB), refactor-module (13.6KB), terraform-stacks (17KB + ~87KB refs), terraform-search-import, azure-verified-modules (16KB), sentinel→policy conversion (with evals), Packer builders | Medium-deep, product-oriented (Stacks/HCP/AVM/Sentinel), not a community-hygiene rulebook |
| Jeffallan/claude-skills | 10.6k / May 2026 | 66 persona skills: devops-engineer, terraform-engineer, kubernetes-specialist, sre-engineer | Shallow per topic: devops-engineer SKILL 6KB; refs terraform-iac 3.2KB, docker-patterns 2.7KB |
| ahmedasmar/devops-claude-skills | 188 / Apr 2026 | 6 plugins: iac-terraform, ci-cd, gitops-workflows, k8s-troubleshooter, monitoring, aws-cost | Medium: iac-terraform SKILL 10.7KB + refs ~41KB + module template, GH-Actions/GitLab/Terragrunt workflows, validator scripts |
| JosiahSiegel/claude-plugin-marketplace | 48 / Jun 2026 | docker-master (docker-best-practices 14KB, docker-2025-features 15KB), terraform-master (agent + tf-plan/apply/state commands + opentofu-guide 15.7KB), azure-to-docker-master (compose-patterns 16KB) | Medium; command/agent-heavy, Windows/git-bash slant |
| Impertio-Studio/Docker-Claude-Skill-Package | 9 / Jul 8 2026 | 22 "deterministic" Docker/Compose skills in 5 families: Dockerfile, multistage, BuildKit, Compose services/resources, security, networking, CI/CD, production | Deep but obscure: 10–14KB per SKILL + ~150KB research fragments; ★9 = near-zero adoption |
| pulumi/agent-skills | 61 / Jul 16 2026 | Official Pulumi: best-practices, components, automation-api, terraform→pulumi migration | Adjacent IaC |
| Mindrally/skills | 192 / Jun 2026 | 240+ Cursor-rule conversions incl terraform/, docker/ | Shallow one-pagers |
| Minor (≤★30) | — | wrsmith108 docker-optimizer, OneWave-AI docker-debugger, cosmicstack-labs docker-patterns, kid-sid containerization, clawic/iliaal/SumonMSelim terraform SKILL.mds, sickn33 github-actions-advanced | Shallow one-file skills |

Directories: skillsmp.com/categories/devops, claudedirectory.org, mcpmarket.com, awesomeskill.ai, claudemarketplaces.com. Press: Pulumi "Top 8 Claude skills for DevOps" (Feb 2026), awsfundamentals on Babenko's skill, Medium "Top 15 Claude Code skills for Terraform devs".

## MCP servers (not skills)

- HashiCorp terraform-mcp-server (official): registry/provider/module doc lookup; ships as the terraform external plugin in claude-plugins-official.
- OneAngryDBA/claude-terraform-lsp-plugin (★1): terraform-ls LSP integration.

## Conclusion

1. Deep prior art EXISTS on the Terraform side: antonbabenko/terraform-skill (★2.2k, active, ~195KB diagnose-first rulebook) already occupies "enterprise Terraform module patterns + hygiene"; hashicorp/agent-skills covers vendor/product surfaces.
2. Docker/compose side is FRAGMENTED AND WEAK: no adopted deep conventions skill — Impertio deep but ★9 and split into 22 micro-skills; JosiahSiegel one 14KB file; rest one-pagers.
3. No awesome-list or official Anthropic surface curates IaC skills; an omniagents-iac would not collide with anything official.
4. Open gap for omniagents-iac: a single opinionated Docker/Dockerfile/compose conventions rulebook at omniagents depth, plus cross-cutting integration (terraform module patterns + compose + CI wiring + env/secrets hygiene as one coherent convention set) — nobody ships that combination; Babenko is Terraform-only and failure-mode-oriented, not an authoring-conventions catalogue.
5. Structure worth borrowing: Babenko's routing-table + on-demand references + response contract; HashiCorp's per-skill eval tasks (evals/tasks/*.yaml); ahmedasmar's assets/ (templates + validator scripts) pattern.
