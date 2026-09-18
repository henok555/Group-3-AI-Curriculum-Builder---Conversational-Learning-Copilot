# TSP Database ER Diagram

```mermaid
erDiagram
    %% Core training hierarchy
    TRAININGS ||--|| AUDIENCE_PROFILES : "has"
    TRAININGS ||--o{ MODULES : "contains"
    TRAININGS ||--o{ OBJECTIVES : "defines"
    TRAININGS ||--o{ ASSESSMENTS : "has"
    TRAININGS ||--o{ SURVEYS : "includes"
    TRAININGS ||--o{ COHORTS : "runs"
    TRAININGS ||--o{ CONTENTS : "requests"
    TRAININGS ||--o{ TRAINEES : "enrolls"
    TRAININGS ||--o{ TRAINING_KEYWORDS : "tagged"
    TRAININGS ||--o{ TRAINING_PURPOSES : "purpose"
    TRAININGS }|--|| COMPANY_PROFILES : "owned_by"
    TRAININGS }|--|| TRAINING_TYPES : "type"

    %% Audience profile details
    AUDIENCE_PROFILES }|--|| EDUCATION_LEVELS : "education"
    AUDIENCE_PROFILES }|--|| LANGUAGES : "language"
    AUDIENCE_PROFILES }|--|| LEARNER_LEVELS : "level"
    AUDIENCE_PROFILES }|--|| WORK_EXPERIENCES : "experience"
    AUDIENCE_PROFILES ||--o{ SPECIFIC_COURSES : "requires"
    AUDIENCE_PROFILES ||--o{ SPECIFIC_PREREQUISITES : "prereqs"

    %% Module hierarchy
    MODULES ||--o{ LESSONS : "contains"
    MODULES }|--|| MODULES : "parent_module"  %% self-ref
    MODULES ||--o{ TRAINING_REFERENCES : "references"
    MODULES ||--o{ MODULE_CONTENT_ITEMS : "schedules"
    MODULES ||--o{ MODULES_INSTRUCTIONAL_METHODS : "uses"
    MODULES ||--o{ MODULE_DIGITAL_TOOLS : "tools"
    MODULES ||--o{ MODULE_PRIMARY_MATERIALS : "primary_material"
    MODULES ||--o{ MODULE_SECONDARY_MATERIALS : "secondary_material"
    MODULES ||--o{ MODULES_ASSESSMENT_TYPES : "assessment_type"
    MODULES ||--o{ MODULES_USERS : "assigned_to"
    MODULES }|--|| TECHNOLOGY_INTEGRATIONS : "integration"
    MODULES }|--|| TRAINING_TAGS : "tag"

    %% Lesson details
    LESSONS ||--o{ LESSON_INSTRUCTIONAL_METHODS : "methods"
    LESSONS ||--o{ LESSON_TECHNOLOGY_INTEGRATIONS : "tech"

    %% Content (Content Requests)
    CONTENTS }|--|| USERS : "developer"
    CONTENTS }|--|| MODULES : "for_module"
    CONTENTS }o--|| LESSONS : "for_lesson"
    CONTENTS }o--|| ASSESSMENTS : "for_assessment"

    %% Assessment structure
    ASSESSMENTS ||--o{ ASSESSMENT_SECTIONS : "sections"
    ASSESSMENT_SECTIONS ||--o{ ASSESSMENT_ENTRIES : "questions"
    ASSESSMENT_ENTRIES ||--o{ ASSESSMENT_ENTRY_CHOICES : "choices"
    ASSESSMENTS }|--|| USERS : "developer"
    ASSESSMENTS }|--|| TRAININGS : "for_training"

    %% Survey structure
    SURVEYS }|--|| SESSIONS : "in_session"
    SURVEYS ||--o{ SURVEY_SECTIONS : "sections"
    SURVEY_SECTIONS ||--o{ SURVEY_ENTRIES : "questions"
    SURVEY_ENTRIES ||--o{ SURVEY_ENTRY_CHOICES : "choices"

    %% Objectives & Outcomes
    OBJECTIVES }|--|| TRAININGS : "for_training"
    OBJECTIVES }|--|| OBJECTIVES : "parent_objective"
    OBJECTIVES ||--o{ OUTCOMES : "outcomes"

    %% Users & Roles
    USERS }|--|| ROLES : "has_role"
    USERS ||--o{ TRAINEES : "trainee_profile"
    TRAINEES }|--|| TRAININGS : "in_training"
    TRAINEES }|--|| COHORTS : "in_cohort"
    TRAINEES }|--|| ACADEMIC_LEVELS : "academic"
    TRAINEES }|--|| LANGUAGES : "language"
    TRAINEES }|--|| CITIES : "city"
    TRAINEES }|--|| ZONES : "zone"

    %% Cohort & Session runtime
    COHORTS }|--|| TRAININGS : "for_training"
    SESSIONS }|--|| COHORTS : "in_cohort"
    SESSIONS }|--|| MODULES : "covers_module"
    SESSIONS }|--|| TRAINERS : "led_by"

    %% AI Responses (existing)
    AI_RESPONSES }|--|| TRAININGS : "for_training"

    %% Key entity definitions
    TRAININGS {
        uuid id PK
        text title
        text executive_summary
        text rationale
        text scope
        varchar delivery_method
        double duration
        varchar duration_type
        date start_date
        date end_date
        uuid company_profile_id FK
        uuid training_type_id FK
        boolean is_deleted
    }

    AUDIENCE_PROFILES {
        uuid id PK
        uuid training_id FK UNIQUE
        uuid education_level_id FK
        uuid language_id FK
        uuid learner_level_id FK
        uuid work_experience_id FK
        text certifications
        text licenses
    }

    MODULES {
        uuid id PK
        uuid training_id FK
        uuid module_id FK  %% self-ref
        varchar name
        text description
        text key_concepts
        integer module_order
    }

    LESSONS {
        uuid id PK
        uuid module_id FK
        varchar name
        text description
        text objective
        double duration
        varchar duration_type
    }

    CONTENTS {
        uuid id PK
        uuid module_id FK
        uuid lesson_id FK
        uuid assessment_id FK
        uuid user_id FK
        varchar name
        varchar file_type  %% PDF, VIDEO, LINK
        varchar level      %% MODULE, LESSON, ASSESSMENT
        varchar status     %% PENDING, ACCEPTED, REJECTED
        text link
        text description
    }

    ASSESSMENTS {
        uuid id PK
        uuid training_id FK
        uuid content_developer_id FK
        varchar name
        varchar assessment_type  %% PRE_POST, CAT, OTHER
        varchar assessment_target %% INDIVIDUAL, GROUP
        varchar assessment_approval_status
        integer duration
        boolean is_timed
    }

    ASSESSMENT_SECTIONS {
        uuid id PK
        uuid assessment_id FK
        varchar title
        integer section_number
    }

    ASSESSMENT_ENTRIES {
        uuid id PK
        uuid section_id FK
        text question
        varchar question_type  %% TEXT, RADIO, CHECKBOX, FILE_UPLOAD
        numeric weight
        integer question_number
    }

    OBJECTIVES {
        uuid id PK
        uuid training_id FK
        uuid objective_id FK  %% parent
        text definition
    }

    OUTCOMES {
        uuid id PK
        uuid objective_id FK
        text definition
    }

    USERS {
        uuid id PK
        varchar email
        varchar username UK
        varchar first_name
        varchar last_name
        uuid role_id FK
        boolean is_active
    }

    ROLES {
        uuid id PK
        varchar name UK  %% CURRICULUM_ADMIN, CONTENT_DEVELOPER, etc.
    }

    TRAINEES {
        uuid id PK
        uuid user_id FK
        uuid training_id FK
        uuid cohort_id FK
        varchar first_name
        varchar last_name
        varchar email
        date date_of_birth
        varchar gender
        varchar employment_status
        uuid academic_level_id FK
        uuid language_id FK
    }

    %% Base data reference tables (simplified)
    EDUCATION_LEVELS { uuid id PK, varchar name, text description }
    LANGUAGES { uuid id PK, varchar name, varchar code }
    LEARNER_LEVELS { uuid id PK, varchar name, text description }
    WORK_EXPERIENCES { uuid id PK, varchar name, text description }
    INSTRUCTIONAL_METHODS { uuid id PK, varchar name, text description }
    TECHNOLOGY_INTEGRATIONS { uuid id PK, varchar name, text description }
    ASSESSMENT_TYPES { uuid id PK, varchar name }
    TRAINING_PURPOSES { uuid id PK, varchar name }
    TRAINING_TAGS { uuid id PK, varchar name }
    TECHNOLOGY_INTEGRATIONS { uuid id PK, varchar name, text description }
    COMPANY_PROFILES { uuid id PK, varchar name, varchar verification_status }
    TRAINING_TYPES { uuid id PK, varchar name }
    COHORTS { uuid id PK, uuid training_id FK, varchar name, date start_date }
    SESSIONS { uuid id PK, uuid cohort_id FK, uuid module_id FK }
    ACADEMIC_LEVELS { uuid id PK, varchar name }
    CITIES { uuid id PK, varchar name }
    ZONES { uuid id PK, varchar name }
```
