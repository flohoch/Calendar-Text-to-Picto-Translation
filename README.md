# Calendar-Text-to-Picto-Translation

A hybrid pipeline that translates calendar event data into [ARASAAC](https://arasaac.org) pictograms. Built as a full-stack application with an **Angular** frontend, a **Java / Spring Boot** backend, and **MongoDB** for pictogram storage.

The system follows the tiered architecture described in the AAC research literature: a curated keyword-matching core ensures deterministic, reliable output for accessibility-critical users, with room to extend toward lemmatization and API-fallback tiers.

---

## Architecture

```
┌────────────┐        ┌────────────────┐        ┌──────────┐
│  Angular   │──────▶│  Spring Boot    │──────▶│ MongoDB  │
│  Frontend  │ REST   │   Backend      │ query  │           │
│  (Nginx)   │◀──────│  /api/translate │◀──────│ 25 000+   │
│  :3000     │  JSON  │  :8080         │        │ pictograms│
└────────────┘        └────────────────┘        └───────────┘
                                                   ▲
                                                   │ seed
                                              ┌────┴───────┐
                                              │ Data Loader│
                                              │ (Python)   │
                                              └────────────┘
                                                   ▲
                                                   │ HTTP
                                              ARASAAC API
```

| Service        | Technology          | Port  | Purpose                                       |
|----------------|---------------------|-------|-----------------------------------------------|
| `mongodb`      | MongoDB 7           | 27017 | Stores all ARASAAC pictogram records          |
| `data-loader`  | Python 3.12         | —     | Fetches pictograms from ARASAAC API → MongoDB |
| `backend`      | Java 21, Spring Boot 3.4 | 8080 | Translation pipeline (keyword matching)   |
| `frontend`     | Angular 19          | 3000  | Calendar event input & pictogram display      |

## Translation Pipeline

The backend currently implements **Tier 1** of the hybrid architecture:

1. **Input normalization** — lowercase and split on whitespace.
2. **Exact keyword matching** — each token is matched against the `searchTerms` index in MongoDB. This index contains all lowercased keywords, plurals, tags, and categories from the ARASAAC database.
3. **Result assembly** — matched pictograms are returned with image URLs; unmatched tokens are flagged.

Future tiers (not yet implemented):
- **Tier 2**: Lemmatization + ARASAAC API fallback for unseen word forms.
- **Tier 3**: Human review queue / constrained neural model for edge cases.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)
- Internet connection (first run fetches ~25 000 pictograms from the ARASAAC API)

## Quick Start

```bash
# Clone the repository
git clone https://github.com/<your-username>/pictogram-translator.git
cd pictogram-translator

# Build and start all services
docker compose up --build

# Wait for the data-loader to finish (watch its logs):
#   "Inserting 25xxx pictograms into MongoDB ..."
#   "Data loading complete."

# Open the frontend
open http://localhost:3000
```

The data loader runs once and exits. On subsequent starts, it detects the existing collection and skips the import.

## Usage

1. Open **http://localhost:3000** in your browser.
2. Enter calendar event details in the three fields:
    - **Summary** — what the event is (e.g., `Essen Frühstück`)
    - **Location** — where it takes place (e.g., `Schule`)
    - **Participants** — who is involved (e.g., `Mutter Vater`)
3. Click **Translate to Pictograms**.
4. Each field shows matched pictograms with images and labels, plus any tokens that couldn't be matched.

## API Reference

### `POST /api/translate`

Translate a calendar event into pictograms.

**Request body:**
```json
{
  "summary": "eat breakfast",
  "location": "school",
  "participants": "mother"
}
```

**Response:**
```json
{
  "summary": {
    "originalText": "eat breakfast",
    "matches": [
      {
        "matchedTerm": "eat",
        "pictogramId": 6456,
        "imageUrl": "https://static.arasaac.org/pictograms/6456/6456_500.png",
        "keywords": [...]
      }
    ],
    "unmatchedTokens": []
  },
  "location": { ... },
  "participants": { ... }
}
```

### `GET /api/pictograms/{id}`

Retrieve a single pictogram by its ARASAAC ID.

### `GET /api/status`

Health check returning `{ "status": "ok", "pictogramCount": 25000 }`.

## Configuration

| Environment Variable        | Default                              | Description                        |
|-----------------------------|--------------------------------------|------------------------------------|
| `SPRING_DATA_MONGODB_URI`   | `mongodb://localhost:27017/pictograms` | MongoDB connection string (backend) |
| `MONGO_URI`                 | `mongodb://localhost:27017`          | MongoDB connection string (loader)  |
| `MONGO_DB`                  | `pictograms`                         | Database name (loader)              |
| `ARASAAC_LANGUAGE`          | `de`                                 | Language code for ARASAAC API       |

To change the pictogram language, set `ARASAAC_LANGUAGE` in `docker-compose.yml` (e.g., `en`, `es`, `fr`).

## Development

### Run services individually

```bash
# Start MongoDB
docker compose up mongodb -d

# Run data loader
docker compose up data-loader

# Backend (requires Java 21 + Maven)
cd backend
mvn spring-boot:run

# Frontend (requires Node 20+)
cd frontend
npm install
npm start    # → http://localhost:4200 with API proxy to :8080
```

### Re-seed the database

```bash
# Drop the collection and re-import
docker compose exec mongodb mongosh pictograms --eval "db.pictograms.drop()"
docker compose up data-loader
```

## Project Structure

```
pictogram-translator/
├── docker-compose.yml
├── data-loader/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── load_pictograms.py        # ARASAAC API → MongoDB
├── backend/
│   ├── Dockerfile
│   ├── pom.xml
│   └── src/main/java/com/pictogramtranslator/
│       ├── PictogramTranslatorApplication.java
│       ├── config/WebConfig.java               # CORS
│       ├── controller/TranslationController.java
│       ├── model/
│       │   ├── Keyword.java
│       │   ├── Pictogram.java
│       │   ├── PictogramMatch.java
│       │   ├── TranslationRequest.java
│       │   └── TranslationResponse.java
│       ├── repository/PictogramRepository.java
│       └── service/TranslationService.java
└── frontend/
    ├── Dockerfile
    ├── nginx.conf
    ├── angular.json
    ├── tsconfig.json
    ├── tsconfig.app.json
    ├── package.json
    ├── proxy.conf.json
    └── src/
        ├── main.ts
        ├── index.html
        ├── styles.css
        └── app/
            ├── app.component.ts
            ├── app.config.ts
            ├── models/
            │   └── translation.model.ts
            ├── services/
            │   └── translation.service.ts
            └── components/
                ├── event-field-input/
                │   └── event-field-input.component.ts
                └── pictogram-results/
                    └── pictogram-results.component.ts
```

## License & Attribution

Pictograms are property of the Government of Aragón and are created by Sergio Palao for [ARASAAC](https://arasaac.org), distributed under the [Creative Commons BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) license.

Application code is licensed under the [MIT License](LICENSE).
