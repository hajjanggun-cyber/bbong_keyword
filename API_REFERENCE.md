# 데이터 수집기 API 참조

각 소스별 필요한 API 및 인증 정보입니다. **API 키/시크릿은 환경 변수로 관리**하세요.

---

## ① 유튜브 (YouTube API)

| 항목 | 내용 |
|------|------|
| **API** | YouTube Data API v3 |
| **인증** | API Key (공개 데이터용) |
| **발급** | [Google Cloud Console](https://console.cloud.google.com) |
| **할당량** | 기본 10,000 쿼리/일 |
| **문서** | https://developers.google.com/youtube/v3/docs |

### 발급 절차
1. Google Cloud Console → 새 프로젝트 생성
2. **API 및 서비스 > 라이브러리** → "YouTube Data API v3" 검색 → 사용
3. **사용자 인증정보 > 만들기** → API 키 선택

### 환경 변수
```
YOUTUBE_API_KEY=your_api_key_here
```

---

## ② 구글 뉴스 (RSS / News API)

### 옵션 A: RSS (무료, API 키 불필요)
- **방식**: Google News RSS URL 파싱
- **도구**: `feedparser` 라이브러리
- **예시**: `https://news.google.com/rss/search?q=급락+단독+최초&hl=ko`
- **장점**: 비용 없음
- **단점**: 구조·안정성 제한

### 옵션 B: NewsAPI.org (유료, 무료 티어 있음)
| 항목 | 내용 |
|------|------|
| **API** | News API |
| **인증** | API Key |
| **가입** | https://newsapi.org |
| **무료** | 개발용 100 요청/일 |
| **문서** | https://newsapi.org/docs |

### 옵션 C: GNews API
- Google News 스타일 랭킹
- https://gnews.io

### 환경 변수 (API 사용 시)
```
NEWS_API_KEY=your_news_api_key_here
```

---

## ③ 네이버 데이터랩 & 뉴스

네이버는 **하나의 애플리케이션**으로 여러 API를 사용합니다.

| 항목 | 내용 |
|------|------|
| **발급** | [네이버 개발자센터](https://developers.naver.com/) |
| **인증** | Client ID + Client Secret |
| **방식** | HTTP 헤더에 `X-Naver-Client-Id`, `X-Naver-Client-Secret` 포함 |

### 필요한 API

| 용도 | API | 할당량 |
|------|-----|--------|
| 분야별 인기 검색어 | **데이터랩 - 통합검색어 트렌드** | 1,000회/일 |
| 뉴스 제목 수집 | **검색 API - 뉴스** | 25,000회/일 |
| 가장 많이 본 뉴스 | 검색 API로 키워드 검색 후 정렬, 또는 실시간 랭킹 스크래핑 |

> ⚠️ "가장 많이 본 뉴스" 전용 API는 없습니다.  
> 검색 API로 수집하거나, 해당 페이지 스크래핑이 필요할 수 있습니다.

### 환경 변수
```
NAVER_CLIENT_ID=your_client_id
NAVER_CLIENT_SECRET=your_client_secret
```

---

## 요약: 필요한 키/시크릿

| 소스 | 필요 항목 | 발급처 |
|------|-----------|--------|
| 유튜브 | `YOUTUBE_API_KEY` | Google Cloud Console |
| 구글 뉴스 (RSS) | 없음 | - |
| 구글 뉴스 (API) | `NEWS_API_KEY` | newsapi.org |
| 네이버 | `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | 네이버 개발자센터 |

---

## .env 예시 (프로젝트 루트에 생성)

```env
# 유튜브
YOUTUBE_API_KEY=

# 구글 뉴스 (API 사용 시)
NEWS_API_KEY=

# 네이버
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=
```

> `.env` 파일은 `.gitignore`에 추가하여 커밋하지 마세요.
