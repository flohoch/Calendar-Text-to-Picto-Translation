import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { TranslationRequest, TranslationResponse } from '../models/translation.model';

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

  getStatus(): Observable<{ status: string; pictogramCount: number }> {
    return this.http.get<{ status: string; pictogramCount: number }>(
      `${this.apiUrl}/status`
    );
  }
}
