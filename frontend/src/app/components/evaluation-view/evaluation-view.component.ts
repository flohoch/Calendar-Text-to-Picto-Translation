import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslationService } from '../../services/translation.service';
import {
  EvaluationEntry,
  EvaluationRun,
  EvaluationRunSummary,
  Language,
  PictogramMatch,
} from '../../models/translation.model';
import { LanguageSelectorComponent } from '../language-selector/language-selector.component';

@Component({
  selector: 'app-evaluation-view',
  standalone: true,
  imports: [CommonModule, LanguageSelectorComponent],
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

        <h4>Precision · Recall · F1</h4>
        <p class="prf-hint">
          <strong>Slot-based</strong> rewards covering each target slot at least once
          (alternatives within a bracket count as one slot).
          <strong>Per-prediction</strong> demands every individual target ID be predicted
          (alternatives don't grant credit to each other) — strictly tougher than slot-based.
          Precision is identical between the two; only Recall and F1 differ.
        </p>
        <div class="prf-pair">
          <div class="prf-block">
            <h5>Slot-based</h5>
            <table class="prf-table">
              <thead>
              <tr><th></th><th>Precision</th><th>Recall</th><th>F1</th></tr>
              </thead>
              <tbody>
              <tr>
                <td>Summary</td>
                <td>{{ pct(selectedRun.metrics.precision_summary) }}</td>
                <td>{{ pct(selectedRun.metrics.recall_summary) }}</td>
                <td>{{ pct(selectedRun.metrics.f1_summary) }}</td>
              </tr>
              <tr>
                <td>Location</td>
                <td>{{ pct(selectedRun.metrics.precision_location) }}</td>
                <td>{{ pct(selectedRun.metrics.recall_location) }}</td>
                <td>{{ pct(selectedRun.metrics.f1_location) }}</td>
              </tr>
              <tr>
                <td>Attendees</td>
                <td>{{ pct(selectedRun.metrics.precision_attendees) }}</td>
                <td>{{ pct(selectedRun.metrics.recall_attendees) }}</td>
                <td>{{ pct(selectedRun.metrics.f1_attendees) }}</td>
              </tr>
              <tr class="macro-row">
                <td>Macro</td>
                <td>{{ pct(selectedRun.metrics.precision_macro) }}</td>
                <td>{{ pct(selectedRun.metrics.recall_macro) }}</td>
                <td>{{ pct(selectedRun.metrics.f1_macro) }}</td>
              </tr>
              </tbody>
            </table>
          </div>

          <div class="prf-block">
            <h5>Per-prediction</h5>
            <table class="prf-table">
              <thead>
              <tr><th></th><th>Precision</th><th>Recall</th><th>F1</th></tr>
              </thead>
              <tbody>
              <tr>
                <td>Summary</td>
                <td>{{ pct(selectedRun.metrics.pp_precision_summary) }}</td>
                <td>{{ pct(selectedRun.metrics.pp_recall_summary) }}</td>
                <td>{{ pct(selectedRun.metrics.pp_f1_summary) }}</td>
              </tr>
              <tr>
                <td>Location</td>
                <td>{{ pct(selectedRun.metrics.pp_precision_location) }}</td>
                <td>{{ pct(selectedRun.metrics.pp_recall_location) }}</td>
                <td>{{ pct(selectedRun.metrics.pp_f1_location) }}</td>
              </tr>
              <tr>
                <td>Attendees</td>
                <td>{{ pct(selectedRun.metrics.pp_precision_attendees) }}</td>
                <td>{{ pct(selectedRun.metrics.pp_recall_attendees) }}</td>
                <td>{{ pct(selectedRun.metrics.pp_f1_attendees) }}</td>
              </tr>
              <tr class="macro-row">
                <td>Macro</td>
                <td>{{ pct(selectedRun.metrics.pp_precision_macro) }}</td>
                <td>{{ pct(selectedRun.metrics.pp_recall_macro) }}</td>
                <td>{{ pct(selectedRun.metrics.pp_f1_macro) }}</td>
              </tr>
              </tbody>
            </table>
          </div>
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

            <!-- SUMMARY field with targets -->
            <div class="field-block">
              <div class="field-block-header">
                <span class="field-block-title">Summary</span>
                <span class="field-block-original">"{{ e.summary }}"</span>
              </div>
              <ng-container *ngTemplateOutlet="targetSlots; context: {
                groups: e.expected_summary,
                predicted: predictedIds(e.response.summary.matches)
              }"></ng-container>
              <ng-container *ngTemplateOutlet="pictoRow; context: {
                matches: e.response.summary.matches,
                groups: e.expected_summary
              }"></ng-container>
              <div *ngIf="e.response.summary.unmatchedTokens?.length" class="unmatched">
                ⚠ Unmatched: <span *ngFor="let t of e.response.summary.unmatchedTokens">{{ t }}</span>
              </div>
            </div>

            <!-- LOCATION field with targets -->
            <div class="field-block">
              <div class="field-block-header">
                <span class="field-block-title">Location</span>
                <span class="field-block-original">"{{ e.location }}"</span>
              </div>
              <ng-container *ngTemplateOutlet="targetSlots; context: {
                groups: e.expected_location,
                predicted: predictedIds(e.response.location.matches)
              }"></ng-container>
              <ng-container *ngTemplateOutlet="pictoRow; context: {
                matches: e.response.location.matches,
                groups: e.expected_location
              }"></ng-container>
              <div *ngIf="e.response.location.unmatchedTokens?.length" class="unmatched">
                ⚠ Unmatched: <span *ngFor="let t of e.response.location.unmatchedTokens">{{ t }}</span>
              </div>
            </div>

            <!-- ATTENDEES field with targets -->
            <div class="field-block">
              <div class="field-block-header">
                <span class="field-block-title">Attendees</span>
                <span class="field-block-original">"{{ e.attendees }}"</span>
              </div>
              <ng-container *ngTemplateOutlet="targetSlots; context: {
                groups: e.expected_attendees,
                predicted: attendeePredictedIds(e)
              }"></ng-container>
              <div *ngIf="e.response.attendees.length === 0" class="empty-field">No attendees</div>
              <div class="attendee-row" *ngFor="let att of e.response.attendees">
                <div class="attendee-label">{{ att.originalAttendee }}</div>
                <ng-container *ngTemplateOutlet="pictoRow; context: {
                  matches: att.matches,
                  groups: e.expected_attendees
                }"></ng-container>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== Reusable templates ===== -->

    <!-- Target slot summary: shows each bracket and whether it's hit -->
    <ng-template #targetSlots let-groups="groups" let-predicted="predicted">
      <div *ngIf="groups?.length" class="target-slots">
        <span class="targets-label">Targets:</span>
        <span class="slot" *ngFor="let g of groups; let i = index"
              [class.slot-hit]="slotHit(g, predicted)"
              [class.slot-miss]="!slotHit(g, predicted)">
          <span class="slot-num">slot {{ i + 1 }}</span>
          <span class="slot-status">{{ slotHit(g, predicted) ? '✓' : '✗' }}</span>
          <span class="slot-ids">[{{ g.join(', ') }}]</span>
        </span>
      </div>
    </ng-template>

    <!-- Picto card row, with hit/miss highlighting against targets -->
    <ng-template #pictoRow let-matches="matches" let-groups="groups">
      <div class="picto-row" *ngIf="matches.length > 0; else noMatches">
        <div class="picto-card"
             *ngFor="let m of matches"
             [class.picto-hit]="isHit(m, groups)"
             [class.picto-miss]="hasTargets(groups) && !isHit(m, groups)">
          <img [src]="m.imageUrl" [alt]="m.matchedTerm" loading="lazy" />
          <span class="picto-label">{{ m.matchedTerm }}</span>
          <span class="picto-id">id {{ m.pictogramId }}</span>
          <span class="match-type" [ngClass]="'mt-' + m.matchType.toLowerCase()">
            {{ m.matchType }}
          </span>
          <span class="confidence">conf {{ m.confidence | number: '1.2-2' }}</span>
          <span class="picto-hit-badge" *ngIf="isHit(m, groups)">✓ in target</span>
        </div>
      </div>
      <ng-template #noMatches>
        <p class="empty-field">No pictogram matches</p>
      </ng-template>
    </ng-template>
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

      .prf-hint {
        color: #555; font-size: 0.85rem; line-height: 1.5;
        margin-bottom: 0.6rem;
      }
      .prf-pair {
        display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;
        margin-bottom: 1rem;
      }
      @media (max-width: 720px) {
        .prf-pair { grid-template-columns: 1fr; }
      }
      .prf-block h5 {
        margin: 0 0 0.4rem 0; font-size: 0.95rem;
        color: #16213e; font-weight: 600;
      }
      .prf-table {
        width: 100%; border-collapse: collapse; background: #fff;
        border-radius: 8px; overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
      }
      .prf-table th, .prf-table td {
        text-align: left; padding: 0.5rem 0.8rem;
        border-bottom: 1px solid #eee; font-size: 0.9rem;
      }
      .prf-table th { background: #f6f6ff; font-weight: 600; }
      .prf-table .macro-row { font-weight: 700; background: #fafaff; }

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

      .field-block {
        background: #fff; border-radius: 8px; padding: 0.85rem;
        margin-bottom: 0.75rem; border: 1px solid #eee;
      }
      .field-block-header {
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 0.5rem;
      }
      .field-block-title { font-weight: 600; color: #16213e; font-size: 0.95rem; }
      .field-block-original { font-size: 0.85rem; color: #777; font-style: italic; }

      .target-slots {
        display: flex; flex-wrap: wrap; gap: 0.4rem;
        margin-bottom: 0.6rem; align-items: center;
      }
      .targets-label { font-size: 0.78rem; color: #555; font-weight: 600; }
      .slot {
        display: inline-flex; align-items: center; gap: 0.3rem;
        padding: 0.2rem 0.5rem; border-radius: 6px;
        font-size: 0.78rem; font-family: ui-monospace, monospace;
      }
      .slot-hit  { background: #d1fae5; color: #065f46; border: 1px solid #6ee7b7; }
      .slot-miss { background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }
      .slot-num { font-weight: 600; text-transform: uppercase; font-size: 0.7rem; }
      .slot-status { font-weight: 700; }
      .slot-ids { opacity: 0.85; }

      .picto-row { display: flex; flex-wrap: wrap; gap: 0.7rem; }
      .picto-card {
        display: flex; flex-direction: column; align-items: center;
        width: 130px; text-align: center; padding: 0.4rem;
        border: 2px solid #eee; border-radius: 8px;
        position: relative;
      }
      .picto-card.picto-hit { border-color: #6ee7b7; background: #ecfdf5; }
      .picto-card.picto-miss { border-color: #fca5a5; background: #fef2f2; }
      .picto-card img {
        width: 90px; height: 90px; object-fit: contain;
        background: #fafafa; padding: 4px; border-radius: 6px;
      }
      .picto-label { margin-top: 0.3rem; font-size: 0.78rem; color: #555; word-break: break-word; }
      .picto-id { font-size: 0.7rem; color: #888; }
      .match-type {
        margin-top: 0.25rem; font-size: 0.62rem; font-weight: 700;
        padding: 0.1rem 0.4rem; border-radius: 4px; letter-spacing: 0.3px;
      }
      .mt-exact         { background: #d1fae5; color: #065f46; }
      .mt-sliding_window{ background: #c7f5e8; color: #035e54; }
      .mt-lexical_dict  { background: #e0f2fe; color: #075985; }
      .mt-disambiguated { background: #cffafe; color: #155e75; }
      .mt-personal_relationship { background: #fef9c3; color: #713f12; }
      .mt-lemma         { background: #dbeafe; color: #1e40af; }
      .mt-compound_split{ background: #ede9fe; color: #5b21b6; }
      .mt-synset        { background: #fef3c7; color: #92400e; }
      .mt-hypernym      { background: #fed7aa; color: #9a3412; }
      .mt-ner_person_fallback { background: #fce7f3; color: #9d174d; }
      .mt-generic_fallback    { background: #f3f4f6; color: #374151; }
      .confidence { font-size: 0.65rem; color: #888; margin-top: 0.15rem; }
      .picto-hit-badge {
        margin-top: 0.2rem; font-size: 0.62rem; color: #065f46;
        font-weight: 700;
      }

      .unmatched { margin-top: 0.5rem; font-size: 0.85rem; color: #b45309; }
      .unmatched span {
        background: #fff3cd; padding: 0.1rem 0.4rem; border-radius: 4px;
        margin-left: 0.3rem; font-weight: 500;
      }

      .attendee-row {
        margin-top: 0.5rem; padding-top: 0.5rem;
        border-top: 1px dashed #eee;
      }
      .attendee-row:first-child { border-top: none; padding-top: 0; }
      .attendee-label {
        font-weight: 600; font-size: 0.85rem;
        margin-bottom: 0.3rem; color: #444;
      }
      .empty-field { color: #aaa; font-style: italic; font-size: 0.9rem; }
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

  // --- Target / hit-detection helpers ---

  predictedIds(matches: PictogramMatch[]): Set<number> {
    return new Set(matches.map((m) => m.pictogramId));
  }

  attendeePredictedIds(e: EvaluationEntry): Set<number> {
    const ids = new Set<number>();
    for (const att of e.response.attendees) {
      for (const m of att.matches) ids.add(m.pictogramId);
    }
    return ids;
  }

  hasTargets(groups: number[][] | null | undefined): boolean {
    return !!(groups && groups.length > 0);
  }

  /** A target slot (bracket) is "hit" if any of its IDs appears in predictions. */
  slotHit(group: number[], predicted: Set<number>): boolean {
    return group.some((id) => predicted.has(id));
  }

  /** A predicted pictogram is "hit" if its ID appears in any target slot. */
  isHit(match: PictogramMatch, groups: number[][] | null | undefined): boolean {
    if (!groups || groups.length === 0) return false;
    for (const g of groups) {
      if (g.includes(match.pictogramId)) return true;
    }
    return false;
  }

  // --- Match-type aggregation ---

  get matchTypeEntries(): { key: string; value: number }[] {
    if (!this.selectedRun) return [];
    return Object.entries(this.selectedRun.metrics.match_type_distribution || {})
      .map(([key, value]) => ({ key, value }))
      .sort((a, b) => b.value - a.value);
  }

  // --- Network ---

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
