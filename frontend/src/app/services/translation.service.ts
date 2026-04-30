import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  EvaluationRun,
  EvaluationRunSummary,
  Language,
  TranslationRequest,
  TranslationResponse,
} from '../models/translation.model';

@Injectable({ providedIn: 'root' })
export class TranslationService {
  private readonly apiUrl = '/api';

  constructor(private http: HttpClient) {}

  translate(request: TranslationRequest): Observable<TranslationResponse> {
    return this.http.post<TranslationResponse>(
      `${this.apiUrl}/translate`,
      request
    );
  }

  runEvaluation(language: Language): Observable<{ filename: string }> {
    return this.http.post<{ filename: string }>(
      `${this.apiUrl}/evaluation/run/${language}`,
      {}
    );
  }

  listEvaluationRuns(): Observable<{ runs: EvaluationRunSummary[] }> {
    return this.http.get<{ runs: EvaluationRunSummary[] }>(
      `${this.apiUrl}/evaluation/runs`
    );
  }

  getEvaluationRun(filename: string): Observable<EvaluationRun> {
    return this.http.get<EvaluationRun>(
      `${this.apiUrl}/evaluation/runs/${filename}`
    );
  }
}
