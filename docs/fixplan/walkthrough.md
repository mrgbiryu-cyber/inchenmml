# 🚀 BUJA Project Walkthrough & Status

## 1. Current Status: Core Stabilization (Phase 1 Complete)
We have successfully stabilized the core infrastructure and fixed critical usability issues.

### ✅ Completed Fixes
1.  **Data Pipeline**:
    *   **File Upload API**: Implemented `POST /api/v1/files/upload`. Connected to Knowledge Ingestion pipeline.
    *   **Port Consistency**: Unified Backend/Frontend on port `8002`.
2.  **UI/UX**:
    *   **Mobile Layout**: Applied `100dvh` for proper mobile viewport handling.
    *   **Enter Guard**: Prevented accidental submissions on mobile devices.

---

## 2. Target State: Advanced Intelligence (Phase 2 Specification)
Based on the **BUJA Master Specification**, we are moving towards a fully intelligent and secure platform.

### 2.1. Conversation Intelligence (✅ Implemented)
- **3-Mode System**:
    - **Natural (Blue)**: Default mode for casual conversation.
    - **Requirement (Green)**: For planning and specs. **Auto-Ingestion** enabled.
    - **Function (Purple)**: For executing tools and commands.
- **Dual Trigger**:
    - **Manual**: Hamburger menu in chat input.
    - **Auto**: Backend detects intent (e.g., "기획해줘" -> Requirement) and signals Frontend to switch mode.
- **Auto-Ingestion**: All assistant responses in Requirement mode are automatically queued for knowledge ingestion.

### 2.2. Data Management
- [ ] **Deduplication**: Check hashes before processing folder uploads.
- [ ] **Seed Knowledge**: Auto-ingest project descriptions upon creation.
- [ ] **Progress Feedback**: Real-time status for bulk uploads.

### 2.3. Security & RBAC
- [ ] **Role Separation**:
    - **Admin**: Full access (Graph/Vector tabs, Agent config).
    - **User**: Chat only. No debug tabs.
- [ ] **Persistence**: `request_id` stored in DB for permanent audit trails.
- [ ] **Source Bar**: Visible only to Admins, persistent across reloads.

### 2.4. UI/UX Evolution
- [ ] **Hierarchy**: Clear `Project > Chat Room` structure.
- [ ] **Navigation**: "New Chat" always visible, Project swipe on mobile.
- [ ] **Clean UI**: No `overflow-x`, consistent header/sidebar layout.

## 3. Verification Guide
### 3.1. Testing Phase 1 (Current)
- **Upload**: `curl -X POST http://localhost:8002/api/v1/files/upload -F "file=@test.txt"` -> Check logs for "Knowledge stored".
- **Mobile**: Open in mobile view -> Check address bar overlap (should be gone) -> Check Enter key behavior.

### 3.2. Testing Phase 2 (Conversation Intelligence)
- **Manual Switch**: Click the hamburger button (left of input) -> Select "Requirement" -> Border turns Green.
- **Auto Switch**: Type "이 프로젝트의 요구사항을 정리해줘" -> Check if mode switches to Green automatically.
- **Auto-Ingestion**: In Requirement mode, ask for a summary -> Check backend logs for "Auto-ingesting Assistant Response".
