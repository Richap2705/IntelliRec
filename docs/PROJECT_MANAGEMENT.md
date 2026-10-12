# IntelliRec — IT Project Management Deliverables

## Scope
Build a web content intelligence and recommendation platform integrating ASTMA analytics, an enterprise REST backend, and a professional web interface.

## Work Breakdown Structure
1. Initiation — problem statement, objectives, feasibility, stakeholders
2. Requirements — functional/non-functional requirements, user stories
3. Architecture — database, API, security, UI and ML architecture
4. Backend — authentication, content, interactions, analytics and APIs
5. ASTMA — social metrics, NLP, sentiment, topics, media analytics
6. Recommendation — content-based, collaborative and hybrid ranking
7. Frontend — user portal, feed, profile and admin analytics
8. Testing — unit, API, integration, usability and model evaluation
9. Deployment — Docker, PostgreSQL and configuration
10. Documentation — report, PPT, viva and user guide

## 12-week schedule
| Week | Deliverable |
|---|---|
| 1 | Problem definition and literature survey |
| 2 | Requirements and feasibility |
| 3 | Architecture and database |
| 4 | Authentication and backend foundation |
| 5 | Content and interaction APIs |
| 6 | Social analytics |
| 7 | NLP and sentiment/topic analytics |
| 8 | Media analytics |
| 9 | Hybrid recommendation engine |
| 10 | Frontend and admin dashboard |
| 11 | Testing, evaluation and deployment |
| 12 | Documentation, PPT and final demo |

## Risks
- Dataset quality: validate and document the source; keep a seeded demo dataset.
- Model quality: evaluate precision/recall/NDCG and compare baselines.
- External dependency failure: core demo runs locally with seeded data.
- Security: secrets in `.env`, password hashing, JWT, role checks.
- Integration delays: keep API contracts stable and test each module independently.

## Mapping to subjects
### ASTMA
Social engagement, sentiment, keywords, topic modelling, content similarity, media metrics and trending analysis.

### Enterprise Systems
Layered FastAPI backend, PostgreSQL, REST APIs, JWT authentication, RBAC, Docker, API documentation and health checks.

### IT Project Management
WBS, schedule, sprint planning, risk register, resource allocation, testing plan and final reporting.
