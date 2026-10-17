# Viva preparation

**What is your contribution?** A working gateway that checks each proposed tool invocation against explicit permissions before it can reach simulated resources. It combines enforcement, human review, and auditable outcomes.

**How is this different from AdaptiveGuard-Bench?** That project evaluates guardrail robustness using adaptive prompt generation. AgentFence implements the authorization boundary that allows, denies, or pauses concrete actions.

**Why is authentication insufficient?** It identifies a caller but does not say which tool, resource, tenant, or operation that caller may use for the assigned task.

**Can the model make itself an administrator?** Not through the proposal contract. Extra role fields are rejected and the server resolves identity from a credential. Protecting the credentials remains essential.

**What does task intent mean here?** A server-assigned operation class, such as investigation or containment. It is not a claim that the gateway understands arbitrary human language.

**Why reject rather than sanitize?** The owner chose the PPT's three outcomes. Silent changes to security-relevant arguments could produce an unintended action. A caller can submit a new valid request explicitly.

**What binds an approval?** A request ID and digest covering exact typed arguments, task, owner, and evidence fingerprints. Arguments cannot be replaced at approval. The gateway rechecks current policy and expires or consumes the request.

**What if two reviewers approve simultaneously?** SQLite serializes the transactions. The first consumes the pending state; the second receives a conflict. A concurrency test verifies one execution.

**What if logging fails?** Mock changes and audit are one transaction, so the change rolls back and the API returns a storage error. Remote systems will need additional idempotency/failure design.

**Are the logs immutable?** No. They are transactional and useful for traceability, but a trusted host administrator can modify the SQLite database. Tamper evidence or an external log sink is future work.

**Have you solved prompt injection?** No. Heuristics can miss rephrased attacks and flag benign quotations. Deterministic authorization still constrains an agent even when suspicious text is not recognized, within the permissions actually configured.

**How do you verify the three objectives?** Functional tests and controlled demonstrations verify gateway mediation, validation and permission rejection, and exact-action approval with audit records. Formal security and performance evaluation is deferred to next semester; it is not a deliverable in this version.

**What remains?** Complete the live Gemini workflow and Windows Docker isolation verification for the current objectives. Richer retrieval and OPA require scope review; formal evaluation belongs to next semester.
