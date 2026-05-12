# GPTimages Index

Last reviewed: 2026-05-12

No new images were generated during this cleanup. This file documents existing generated images, where they are used, and whether they are safe to keep as current visual support.

Important rule: these images support architecture storytelling. They are not evidence that a runtime capability is implemented unless paired with source code, infrastructure code, CI workflow, test output, report, or screenshot.

| File path | Topic | Used in tracked docs | Status | Recommended action |
|---|---|---:|---|---|
| `GPTimages/Architecture.png` | High-level platform architecture | Yes: `README.md`, `case-study.md` | Current conceptual overview | Keep; pair with implementation evidence in `docs/evidence/index.md`. |
| `GPTimages/Architecture-Layers.png` | Layered architecture | Yes: `README.md`, `case-study.md` | Current conceptual overview | Keep; avoid using as proof of implementation. |
| `GPTimages/Business-Product-Perspective.png` | Product/business perspective | Yes: `case-study.md` | Current narrative support | Keep. |
| `GPTimages/Business-Value-Perspective.png` | Business value perspective | Yes: `case-study.md` | Current narrative support | Keep. |
| `GPTimages/Project-Evolution.png` | Project evolution roadmap | Yes: `case-study.md` | Current roadmap support | Keep; review if roadmap phases change. |
| `GPTimages/AWS-Well-Architected-Framework.png` | AWS Well-Architected framing | Yes: `case-study.md` | Current conceptual support | Keep; pair with Terraform and AWS evidence. |
| `GPTimages/AWS-Cloud-Architecture.png` | AWS target architecture | Yes: `case-study.md` | Current target architecture support | Keep; label as target/design unless backed by Terraform evidence. |
| `GPTimages/Microservices-Architecture.png` | Microservices architecture | Yes: `case-study.md` | Current conceptual support | Keep; avoid overclaiming deployed microservices. |
| `GPTimages/Data-Flow-Intelligence-Lifecycle.png` | Data and intelligence lifecycle | Yes: `case-study.md` | Current conceptual support | Keep; pair with data generator and API evidence. |
| `GPTimages/CI-CD-Pipeline-Delivery-Workflow.png` | CI/CD delivery workflow | Yes: `README.md`, `case-study.md` | Current conceptual support | Keep; pair with GitHub Actions, Jenkinsfile, and reports. |
| `GPTimages/Security-Governance-Architecture.png` | Security and governance architecture | Yes: `case-study.md` | Current conceptual support | Keep; pair with security workflows and scan reports. |
| `GPTimages/Observability-Operational-Control.png` | Observability and operations | Yes: `case-study.md` | Current conceptual support | Keep; add real dashboard screenshots when available. |
| `GPTimages/Reliability-Scalability-Cost-Control.png` | Reliability, scalability, cost control | Yes: `case-study.md` | Current conceptual support | Keep; pair with FinOps and cleanup evidence. |
| `GPTimages/Executive-Architecture-Summary.png` | Executive architecture summary | Yes: `case-study.md` | Current narrative support | Keep. |
| `GPTimages/Enterprise-Scorecard.png` | Enterprise scorecard | Yes: `docs/enterprise-scorecard.md` | Current narrative support | Keep; update if scorecard statuses change. |
| `GPTimages/User-Groups-Decision-Needs.png` | User groups and decision needs | Yes: `docs/user-groups.md` | Current narrative support | Keep. |
| `GPTimages/Workflow-Operating-Model.png` | Workflow operating model | Yes: `docs/workflows.md` | Current narrative support | Keep. |
| `GPTimages/retailops_domain_model_diagram_overview.png` | Domain model overview | Yes: `docs/data-model.md` | Current conceptual support | Keep; verify against data model after schema changes. |
| `GPTimages/retailops_testing_roadmap_infographic.png` | Testing roadmap infographic | No tracked doc reference found except repository structure snapshot | Unused | Keep as archive for now; either reference from testing docs or remove in a future cleanup. |
| `GPTimages/Data-Flow.png` | Alternative data-flow visual | No tracked doc reference found except repository structure snapshot | Unused | Keep as archive for now; remove later if superseded by `Data-Flow-Intelligence-Lifecycle.png`. |
| `GPTimages/Future-Growth-Perspective.png` | Future growth perspective | No tracked doc reference found except repository structure snapshot | Unused | Keep as archive for now; reference only if a future roadmap page needs it. |

## Maintenance Notes

- Keep filenames stable unless all references are updated in the same change.
- Prefer Markdown/Mermaid diagrams for implementation-specific flows because they are easier to diff and keep current.
- Use GPT images for portfolio storytelling, not for audit claims.
- Before deleting unused images, check README, `case-study.md`, docs, slides, and external portfolio pages.
