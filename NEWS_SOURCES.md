# 뉴스·콘텐츠 소스 및 수집 시스템 정리

---

## 개요

| 소스 | 유형 | 수집 방식 | 인증 |
|------|------|-----------|------|
| 유튜브 | 동영상 | API | YOUTUBE_API_KEY 필수 |
| 구글 뉴스 | 기사 | RSS + NewsAPI | NewsAPI 선택 |
| 네이버 뉴스 | 기사 | 웹 스크래핑 | 없음 |

---

## 1. 유튜브 (YouTube)

### 참고하는 콘텐츠
- 국뽕·어그로 관련 키워드가 포함된 **동영상 제목**
- 지식펀치 채널 스타일 주제와 유사한 영상

### 수집 시스템
| 항목 | 내용 |
|------|------|
| **방식** | YouTube Data API v3 (공식 API) |
| **엔드포인트** | `search` → `videos` (조회수·업로드일) |
| **인증** | API Key (Google Cloud Console) |
| **파일** | `youtube_scraper.py` |

### 확인·필터링 조건
| 조건 | 값 |
|------|-----|
| 업로드 시점 | 최근 7일 이내 |
| 최소 조회수 | 10만 회 이상 |
| 검색어 예시 | "한국 국산화 성공", "일본 패닉", "세계 최초", "국세청 조사", "폭락", "몰락" |

### 수집 데이터
- 제목, 영상 URL, 조회수, 업로드일

---

## 2. 구글 뉴스 (Google News)

### 참고하는 콘텐츠
- 실시간 경제·시사 관련 기사
- 어그로성 키워드 포함 헤드라인

### 수집 시스템 A: RSS (무료)
| 항목 | 내용 |
|------|------|
| **방식** | Google News RSS 피드 파싱 |
| **URL** | `https://news.google.com/rss/search?q={키워드}&hl=ko&gl=KR&ceid=KR:ko` |
| **라이브러리** | feedparser |
| **인증** | 없음 |

### 수집 시스템 B: NewsAPI.org (선택)
| 항목 | 내용 |
|------|------|
| **방식** | NewsAPI.org REST API |
| **엔드포인트** | `GET /v2/everything` |
| **인증** | API Key (.env의 NEWS_API_KEY) |
| **사용 조건** | API 키가 설정된 경우에만 사용 |

### 확인·필터링 조건
| 조건 | 값 |
|------|-----|
| 검색어 | "급락", "단독", "최초", "국세청", "폭락" |
| RSS | 한국어(ko), 한국(gl=KR) 기준 |
| NewsAPI | 최근 7일 이내 기사 (from 파라미터) |

### 수집 데이터
- 제목, 기사 URL, 발행일

### 중복 처리
- RSS와 NewsAPI 결과를 **URL 기준**으로 병합 후 중복 제거

---

## 3. 네이버 뉴스 (Naver News)

### 참고하는 콘텐츠
- **가장 많이 본 뉴스** 경제·사회 섹션 기사 제목

### 수집 시스템
| 항목 | 내용 |
|------|------|
| **방식** | HTML 웹 스크래핑 |
| **URL** | `https://news.naver.com/main/ranking/popularDay.naver?sid1={섹션코드}` |
| **라이브러리** | requests + BeautifulSoup |
| **인증** | 없음 |

### 섹션 코드
| 섹션 | sid1 | 수집 건수 |
|------|------|-----------|
| 경제 | 101 | 10건 |
| 사회 | 102 | 10건 |

### 확인·추출 방식
1. HTTP GET으로 HTML 수신
2. `resp.apparent_encoding`으로 인코딩 감지 (한글 깨짐 방지)
3. BeautifulSoup으로 `<a href="...n.news.naver.com/article...">` 링크 탐색
4. 링크 텍스트에서 제목 추출
5. `ntype=RANKING` 포함 링크만 사용

### 제외 대상
- "동영상기사", "이미지", "집계안내", "닫기" 등 짧은/부가 텍스트
- 제목 길이 5자 미만

### 수집 데이터
- 제목, 기사 URL, 섹션(경제/사회)

---

## 4. 어그로 점수 산출 (공통)

모든 소스에서 수집한 제목은 **동일한 어그로 분석기**로 점수화합니다.

| 항목 | 내용 |
|------|------|
| **파일** | `aggro_analyzer.py` |
| **키워드** | `keyword_dict.py` (S/A/B급) |
| **가중치** | S급×3, A급×2, B급×1.5 |

---

## 5. 실행 흐름

```
run_all.py
    ├── youtube_scraper    → API 호출 (YOUTUBE_API_KEY)
    ├── google_news_scraper → RSS 파싱 + NewsAPI (NEWS_API_KEY 선택)
    ├── naver_news_scraper  → HTML 스크래핑
    └── aggro_analyzer      → 점수 부여
         └── excel_reporter → 엑셀 1개 파일 출력
```
