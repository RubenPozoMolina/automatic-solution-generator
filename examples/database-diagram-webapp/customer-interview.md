# Customer Interview

## 📋 Interview Information

| Field | Value |
|-------|-------|
| **Date** | October 20, 2026 |
| **Interviewer** | Product Manager Agent |
| **Product** | Database Diagram Web Application |
| **Language** | English |
| **Status** | Completed |

---

## 1. Product Context

### 1.1 Name & Purpose
**What is the name or main purpose of the application you want to build?**
- database-diagram-webapp. I need an application that allows me to design database diagrams.

---

### 1.2 Problem Statement

**Describe the problem you're trying to solve:**

- The problem we have is that we need a tool that allows us to import and export database models in an agnostic way.
- Models must be exchangeable both through JSON files and directly with a PostgreSQL database.

---

### 1.3 Primary User

**Who will be the main user of this application?**

- database-designer

---

### 1.4 Value Proposition

**What value will this solution provide?**

- Facilitates the creation and editing of database diagrams.

---

## 2. Scope & Features

### 2.1 Main Functionality

**Can you describe the main features you envision for this product?**

- Graphic design. Import and export database models, from and to JSON files and from and to PostgreSQL databases.

---

### 2.2 User Actions

**What can the user do with the application?**

- The user can create and edit database diagrams. They can also save in JSON format and import them from the same format.
- The user can connect to a PostgreSQL database by providing host, port, database, user and password.
- The user can import an existing PostgreSQL schema (tables, columns, data types, primary keys, foreign keys, unique constraints and indexes) and see it as a diagram.
- The user can export a diagram to a PostgreSQL database, creating the tables, keys and relationships in a chosen schema. The application must show the SQL (DDL) it is going to run and ask for confirmation before changing the database; existing objects are never dropped.
- Database credentials are used only for the current session: they are never stored or written to the JSON files.

---

### 2.3 Priority Classification

**Are there specific features that are essential vs. desirable?**

- **Must-have (Essential):**
- Graphic design. Import and export database models in JSON format.
- Connection to PostgreSQL to import existing schemas as diagrams and to export diagrams as schemas.
  
- **Nice-to-have (Desirable):**
  Connection with other known databases (MySQL, SQL Server, Oracle...). PostgreSQL is the only database required for now.

---

## 3. Users & Target Audience

### 3.1 User Type

**Who will use this solution?**

- [ ] Internal company users
- [X ] Public application users
- [ ] Other: 

---

### 3.2 User Roles

**What user profiles or roles will exist?**

- No roles. The website must be accessible to all users.

---

### 3.3 User Volume

**How many users do you estimate?**

- Local use, no performance problem.

---

## 4. Constraints & Preferences

### 4.1 Technical Constraints

**Are there any technical constraints?**

- **Technology preferences:**
  
- Application is web. Working with JSON files does not need a backend. Connecting to PostgreSQL does: a browser cannot open database connections, so a small backend service is allowed and required for this feature only.
- The backend must be lightweight, run locally and expose a minimal API (test connection, read schema, apply schema). It talks to PostgreSQL 14 or later.
- Database design, schema introspection and DDL generation are handled by a database expert.
- Graphic design. Import and export database models.
- We want to use open-source technologies.
- We need a light web framework.

---

### 4.2 Timeline

**Are there important dates or deadlines we should consider?**

- No

---

### 4.3 Budget

**Are there budget constraints?**

- No

---

## 5. Additional Notes

| Item | Details |
|------|---------|
| Interview date | October 20, 2026 |
| Next steps | Create Product Requirements Document (PRD) |
| Follow-up scheduled | Product roadmap and user stories |

---

## ✅ Interview Summary

All questions completed. Key takeaways:

- **Product:** Database diagram web application
- **Core Features:** Visual graphic design, import/export database models (JSON format and PostgreSQL)
- **User Base:** Public application, single role (no auth required)
- **Tech Stack:** Open-source, lightweight web framework, small local backend only for the PostgreSQL connection
- **Nice-to-have:** Connections to other databases besides PostgreSQL
