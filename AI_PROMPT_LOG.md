# AI Prompt Log – Institutional Event Resource Management System

1. Design a Flask-based institutional event management system with multi-level approval workflow (Coordinator → HOD → Dean → Head).

2. Implement role-based access control using decorators.

3. Create SQLite schema for users, venues, resources, events, approvals, and notifications.

4. Add venue conflict detection logic for overlapping time slots.

5. Implement dynamic resource allocation and automatic release on rejection or completion.

6. Build responsive UI using Tailwind CSS.

7. Deploy Flask application to Render free tier.

# AI Prompt Log – Institutional Event Resource Management System

AI Tool Used: ChatGPT (GPT-4)

---

## 1. System Architecture Design

Prompt:
Design a Flask-based institutional event management system that supports:
- Multi-level approval workflow (Coordinator → HOD → Dean → Institutional Head)
- Role-based access control
- Conflict-free venue allocation
- Resource allocation with validation
- Dynamic state updates

---

## 2. Database Schema Design

Prompt:
Generate SQLite schema for:
- users (with roles)
- venues (capacity-based)
- resources (with total and available quantity)
- events (with approval state tracking)
- event_resources (junction table)
- approvals (audit log)
- notifications (role-based messaging)

---

## 3. Role-Based Access Control

Prompt:
Implement role-based decorators in Flask to:
- Restrict page access based on role
- Prevent bypassing approval hierarchy
- Restrict dashboard visibility per role

---

## 4. Event Validation Logic

Prompt:
Add validation logic for:
- Venue capacity limits
- Overlapping time-slot detection
- Resource availability constraints
- Proper rollback on rejection

---

## 5. Approval Engine

Prompt:
Implement strict approval order:
pending_hod → pending_dean → pending_head → approved

Ensure:
- No skipping levels
- Status updates correctly
- Proper notifications to next approver

---

## 6. Resource Allocation Engine

Prompt:
Design resource deduction logic:
- Deduct resources on approval
- Restore resources on rejection
- Restore resources on completion
- Maintain consistency under concurrency

---

## 7. UI Design

Prompt:
Create a modern, clean dashboard using Tailwind CSS with:
- Role-based UI
- Card-based layout
- Status indicators
- Action buttons for approval

---

## 8. Deployment

Prompt:
Deploy Flask app on Render free tier.
Ensure:
- PORT binding compatibility
- Database initialization on startup
- Environment variable handling

---

## 9. Debugging & Stabilization

Prompt:
Fix issues related to:
- Session handling
- Database persistence
- Login authentication failures
- Render deployment compatibility

---

## Engineering Approach

The AI tool was used for:
- System design structuring
- Database modeling
- Backend implementation
- Validation logic
- Deployment configuration
- Iterative debugging and refinement

All business logic decisions and architectural choices were guided manually and refined iteratively.
