import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslationService } from '../../services/translation.service';
import {
  EvaluationEntry,
  EvaluationRun,
  EvaluationRunSummary,
  Language,
} from '../../models/translation.model';
import { LanguageSelectorComponent } from '../language-selector/language-selector.component';
import { PictogramResultsComponent } from '../pictogram-results/pictogram-results.component';

@Component({
  selector: 'app-evaluation-view',
  standalone: true,
  imports: [CommonModule, LanguageSelectorComponent, PictogramResultsComponent],
  template: `
    <div class="eval-view">
      <h2>Evaluation</h2>
      <p class="hint">
        Run all entries in <code>data/input/calendar_entries_{{ '{' }}lang{{ '}' }}.csv</code>.
        Targets are written as bracket groups, e.g. <code>[12133,4321]</code> (one slot, any of the IDs)
        or <code>[12133,4321],[4239,5439]</code> (two slots — at least one ID from each bracket must appear).
      </p>

      <div class="run-controls">
        <app-language-selector
          [value]="evalLanguage"
          (valueChange)="evalLanguage = $event"
        ></app-language-selector>
        <button class="run-btn" (click)="runEval()" [disabled]="running">
          {{ running ? 'Running…' : '▶ Run Evaluation' }}
        </button>
      </div>

      <div class="error-msg" *ngIf="error">Error: {{ error }}</div>

      <h3>Past Runs</h3>
      <ul class="run-list" *ngIf="runs.length > 0; else noRuns">
        <li
          *ngFor="let r of runs"
          (click)="loadRun(r.filename)"
          [class.active]="selectedFilename === r.filename"
        >
          <strong>{{ r.run_id }}</strong>
          <span class="meta">{{ r.timestamp }} · {{ r.total_entries }} entries</span>
        </li>
      </ul>
      <ng-template #noRuns>
        <p class="empty-field">No evaluation runs yet — click "Run Evaluation" above.</p>
      </ng-template>

      <div *ngIf="selectedRun" class="run-detail">
        <h3>Metrics — {{ selectedRun.run_id }}</h3>
        <div class="metrics-grid">
          <div class="metric"><label>Entries</label><span class="value">{{ selectedRun.metrics.total_entries }}</span></div>
          <div class="metric"><label>Coverage (Summary)</label><span class="value">{{ pct(selectedRun.metrics.coverage_summary) }}</span></div>
          <div class="metric"><label>Coverage (Location)</label><span class="value">{{ pct(selectedRun.metrics.coverage_location) }}</span></div>
          <div class="metric"><label>Coverage (Attendees)</label><span class="value">{{ pct(selectedRun.metrics.coverage_attendees) }}</span></div>
          <div class="metric primary"><label>Accuracy (Summary)</label><span class="value">{{ pct(selectedRun.metrics.accuracy_summary) }}</span></div>
          <div class="metric primary"><label>Accuracy (Location)</label><span class="value">{{ pct(selectedRun.metrics.accuracy_location) }}</span></div>
          <div class="metric primary"><label>Accuracy (Attendees)</label><span class="value">{{ pct(selectedRun.metrics.accuracy_attendees) }}</span></div>
          <div class="metric primary"><label>Accuracy (Overall)</label><span class="value">{{ pct(selectedRun.metrics.accuracy_overall) }}</span></div>
          <div class="metric"><label>Avg Confidence</label><span class="value">{{ selectedRun.metrics.avg_confidence | number:'1.2-2' }}</span></div>
          <div class="metric"><label>Avg Unmatched / Entry</label><span class="value">{{ selectedRun.metrics.avg_unmatched_tokens_per_entry | number:'1.1-2' }}</span></div>
        </div>

        <div class="match-type-dist">
          <h4>Match Type Distribution</h4>
          <div class="mt-bars">
            <div class="mt-bar" *ngFor="let kv of matchTypeEntries">
              <span class="mt-name">{{ kv.key }}</span>
              <span class="mt-count">{{ kv.value }}</span>
            </div>
          </div>
        </div>

        <h3>Entries</h3>
        <div class="entries">
          <div class="entry" *ngFor="let e of selectedRun.entries">
            <div class="entry-header">
              <strong>#{{ e.id }}</strong>
              <span class="lang-badge">{{ e.language }}</span>
              <span *ngIf="e.summary_correct !== null"
                    [class.correct]="e.summary_correct"
                    [class.wrong]="!e.summary_correct">
                summary: {{ e.summary_correct ? '✓' : '✗' }}
              </span>
              <span *ngIf="e.location_correct !== null"
                    [class.correct]="e.location_correct"
                    [class.wrong]="!e.location_correct">
                location: {{ e.location_correct ? '✓' : '✗' }}
              </span>
              <span *ngIf="e.attendees_correct !== null"
                    [class.correct]="e.attendees_correct"
                    [class.wrong]="!e.attendees_correct">
                attendees: {{ e.attendees_correct ? '✓' : '✗' }}
              </span>
            </div>

            <div *ngIf="hasExpected(e)" class="expected-line">
              Expected:
              <span *ngIf="e.expected_summary.length">
                summary {{ formatGroups(e.expected_summary) }}
              </span>
              <span *ngIf="e.expected_location.length">
                · location {{ formatGroups(e.expected_location) }}
              </span>
              <span *ngIf="e.expected_attendees.length">
                · attendees {{ formatGroups(e.expected_attendees) }}
              </span>
            </div>

            <app-pictogram-results label="Summary" [data]="e.response.summary"></app-pictogram-results>
            <app-pictogram-results label="Location" [data]="e.response.location"></app-pictogram-results>
            <app-pictogram-results label="Attendees" [attendees]="e.response.attendees"></app-pictogram-results>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [
    `
      .eval-view { padding: 0.5rem 0; }
      h2 { font-size: 1.5rem; color: #16213e; margin-bottom: 0.3rem; }
      h3 { margin-top: 1.5rem; margin-bottom: 0.6rem; color: #16213e; }
      h4 { margin-top: 1rem; margin-bottom: 0.4rem; }
      .hint { color: #777; font-size: 0.9rem; margin-bottom: 1rem; line-height: 1.5; }
      .hint code {
        background: #f1f1f1; padding: 0.1rem 0.3rem;
        border-radius: 4px; font-size: 0.85rem;
      }
      .run-controls {
        display: flex; align-items: center; gap: 1rem; margin-bottom: 1.5rem;
        background: #fff; padding: 1rem; border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08); flex-wrap: wrap;
      }
      .run-btn {
        padding: 0.6rem 1.2rem; background: #16a34a; color: #fff;
        border: none; border-radius: 8px; font-size: 1rem;
        font-weight: 600; cursor: pointer;
      }
      .run-btn:disabled { opacity: 0.5; cursor: not-allowed; }
      .error-msg {
        background: #ffe0e0; color: #c00; padding: 0.75rem;
        border-radius: 8px; margin-bottom: 1rem;
      }
      .run-list { list-style: none; padding: 0; }
      .run-list li {
        background: #fff; padding: 0.7rem 1rem; margin-bottom: 0.5rem;
        border-radius: 8px; cursor: pointer;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05);
        display: flex; justify-content: space-between; align-items: center;
      }
      .run-list li:hover { background: #f6f6ff; }
      .run-list li.active { background: #e0e7ff; border: 2px solid #4361ee; }
      .meta { color: #888; font-size: 0.85rem; }

      .metrics-grid {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 0.75rem; margin-bottom: 1rem;
      }
      .metric {
        background: #fff; padding: 0.75rem; border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
      }
      .metric.primary { border-left: 4px solid #4361ee; }
      .metric label { display: block; color: #666; font-size: 0.8rem; }
      .metric .value { display: block; font-weight: 700; font-size: 1.2rem; color: #16213e; }

      .mt-bars { display: flex; flex-wrap: wrap; gap: 0.5rem; }
      .mt-bar {
        background: #f6f6ff; padding: 0.4rem 0.7rem; border-radius: 6px;
        font-size: 0.85rem;
      }
      .mt-name { font-weight: 600; }
      .mt-count { color: #4361ee; margin-left: 0.4rem; }

      .entry {
        background: #fafafa; border-radius: 12px; padding: 1rem;
        margin-bottom: 1.5rem; border: 1px solid #eee;
      }
      .entry-header {
        display: flex; gap: 0.6rem; align-items: center; flex-wrap: wrap;
        margin-bottom: 0.6rem; font-size: 0.9rem;
      }
      .lang-badge {
        background: #e5e7eb; padding: 0.1rem 0.5rem; border-radius: 4px;
        font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
      }
      .correct { color: #065f46; font-weight: 600; }
      .wrong { color: #b91c1c; font-weight: 600; }
      .expected-line {
        font-size: 0.8rem; color: #555; margin-bottom: 0.5rem;
        background: #f6f6ff; padding: 0.4rem 0.6rem; border-radius: 6px;
      }
      .empty-field { color: #aaa; font-style: italic; }
    `,
  ],
})
export class EvaluationViewComponent implements OnInit {
  evalLanguage: Language = 'de';
  running = false;
  error: string | null = null;
  runs: EvaluationRunSummary[] = [];
  selectedFilename: string | null = null;
  selectedRun: EvaluationRun | null = null;

  constructor(private svc: TranslationService) {}

  ngOnInit() {
    this.refreshRuns();
  }

  pct(v: number | undefined): string {
    if (v === undefined || v === null) return '—';
    return (v * 100).toFixed(1) + '%';
  }

  hasExpected(e: EvaluationEntry): boolean {
    return !!(
      e.expected_summary?.length ||
      e.expected_location?.length ||
      e.expected_attendees?.length
    );
  }

  formatGroups(groups: number[][]): string {
    if (!groups || groups.length === 0) return '';
    return groups.map((g) => '[' + g.join(', ') + ']').join(' · ');
  }

  get matchTypeEntries(): { key: string; value: number }[] {
    if (!this.selectedRun) return [];
    return Object.entries(this.selectedRun.metrics.match_type_distribution || {})
      .map(([key, value]) => ({ key, value }))
      .sort((a, b) => b.value - a.value);
  }

  refreshRuns() {
    this.svc.listEvaluationRuns().subscribe({
      next: (res) => (this.runs = res.runs),
      error: (e) => (this.error = e.message),
    });
  }

  runEval() {
    this.running = true;
    this.error = null;
    this.svc.runEvaluation(this.evalLanguage).subscribe({
      next: (res) => {
        this.running = false;
        this.refreshRuns();
        this.loadRun(res.filename);
      },
      error: (e) => {
        this.running = false;
        this.error = e?.error?.detail || e.message;
      },
    });
  }

  loadRun(filename: string) {
    this.selectedFilename = filename;
    this.svc.getEvaluationRun(filename).subscribe({
      next: (run) => (this.selectedRun = run),
      error: (e) => (this.error = e.message),
    });
  }
}
