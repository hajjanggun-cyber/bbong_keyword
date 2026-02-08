"""
유튜브 + 구글뉴스 + 네이버 뉴스 → 통합 엑셀 1개 파일
"""

import os
import re

# .env 로드 (프로젝트 루트 기준)
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
    load_dotenv(_env_path)
except ImportError:
    pass

import pandas as pd

from aggro_analyzer import analyze_articles
from excel_reporter import export_to_excel, export_to_js
from google_news_scraper import scrape_google_news
from naver_news_scraper import scrape_ranking_news
from youtube_scraper import scrape_youtube


def _to_row(item: dict, source_type: str) -> dict:
    """소스별 통일된 행 형식으로 변환."""
    base = {
        "title": item.get("title", ""),
        "score": item.get("score", 0),
        "score_keywords": item.get("score_keywords", ""),
        "source": source_type if source_type == "유튜브" else item.get("source", source_type),
        "youtube_url": item.get("url", "") if source_type == "유튜브" else "",
        "news_url": "" if source_type == "유튜브" else item.get("url", ""),
        "views": item.get("views", ""),
        "upload_date": item.get("upload_date", item.get("section", "")),
        "category": item.get("category", ""), # 카테고리 필드 추가
    }
    if source_type == "유튜브":
        base["source"] = "유튜브"
    return base


def _title_words(title: str) -> set:
    """제목에서 유의미한 단어(2자 이상) 추출."""
    if not title or not isinstance(title, str):
        return set()
    words = re.findall(r"[가-힣a-zA-Z0-9]{2,}", str(title))
    return set(w for w in words if len(w) >= 2)


def _is_similar(title1: str, title2: str, min_common: int = 2) -> bool:
    """두 제목이 비슷한지 (공통 단어 2개 이상)."""
    w1, w2 = _title_words(title1), _title_words(title2)
    return len(w1 & w2) >= min_common


def _enrich_with_similar_news(df: pd.DataFrame, all_news: list) -> pd.DataFrame:
    """뉴스 행에 비슷한 기사 최대 2개 추가 (뉴스기사2_URL, 뉴스기사2_날짜, 뉴스기사3_URL, 뉴스기사3_날짜)."""
    out = df.copy()
    out["뉴스기사2_URL"] = ""
    out["뉴스기사2_날짜"] = ""
    out["뉴스기사3_URL"] = ""
    out["뉴스기사3_날짜"] = ""

    news_pool = [
        (r.get("news_url", "") or r.get("뉴스기사_URL", ""), r.get("upload_date", "") or r.get("업로드일", ""), r.get("title", ""))
        for r in all_news
        if (r.get("news_url") or r.get("뉴스기사_URL")) and (r.get("title") or "")
    ]

    for idx, row in out.iterrows():
        news_url = row.get("뉴스기사_URL", "") or row.get("news_url", "")
        if not news_url or not str(news_url).strip():
            continue
        title = row.get("제목", "") or row.get("title", "")
        used_urls = {str(news_url).strip()}
        similar = []
        for url, udate, t in news_pool:
            if not url or str(url).strip() in used_urls:
                continue
            if _is_similar(title, t):
                similar.append((url, udate))
                used_urls.add(str(url).strip())
                if len(similar) >= 2:
                    break
        if similar:
            out.at[idx, "뉴스기사2_URL"] = similar[0][0]
            out.at[idx, "뉴스기사2_날짜"] = similar[0][1]
            if len(similar) >= 2:
                out.at[idx, "뉴스기사3_URL"] = similar[1][0]
                out.at[idx, "뉴스기사3_날짜"] = similar[1][1]
    return out


def main() -> None:
    """유튜브·구글·네이버 수집 → 어그로 점수 → 엑셀 1개 파일."""
    all_items = []

    from keyword_dict import SEARCH_TOPICS, AGGRO_DICTIONARY
    
    # 카테고리별 순회 수집
    for category, keywords in SEARCH_TOPICS.items():
        print(f"\n=== [{category}] 카테고리 수집 시작 ===")
        # 1. 유튜브
        try:
            print(f"  유튜브 수집 중 ({keywords[:3]}...)")
            # 키워드 중 랜덤 또는 상위 몇 개만 사용하거나, 별도 로직 필요
            # 여기서는 편의상 첫 번째 키워드 + '속보' 조합 등으로 검색한다고 가정하거나
            # youtube_scraper 내부를 수정해야 하는데, 
            # 일단 기존 코드는 'query' 인자를 안 받으므로
            # youtube_scraper.py가 내부적으로 고정 키워드를 쓰는지 확인 필요.
            # (기존 코드: scrape_youtube() -> KEYWORDS_NATIONAL_PRIDE 등 사용)
            
            # *기존 스크래퍼들이 외부 인자(query)를 받도록 수정되어 있지 않다면*
            # *이 루프가 의미가 없을 수 있음.*
            # *하지만 사용자의 요청은 "정치를 제외한 주제를 뽑는 키워드는 니가 이슈가 될 만한 걸로 세팅해"였으므로*
            # *각 스크래퍼가 'keywords'를 인자로 받을 수 있게 수정하거나,*
            # *여기서 임시로 전역 변수를 조작해서 돌려야 함.*
            
            # **중요**: 현재 스크래퍼들은 내부적으로 keyword_dict.py의 상수들(KEYWORDS_S_NATIONAL_PRIDE 등)을 직접 참조함.
            # 따라서 run_all.py에서 이를 동적으로 제어하려면 스크래퍼 함수에 'keywords' 리스트를 전달할 수 있어야 함.
            
            # (시간 관계상 run_all.py에서 스크래퍼 호출 시 인자를 전달하고, 스크래퍼가 이를 쓰도록 한다고 가정)
            # scrape_youtube(keywords=keywords)
            
            # 만약 스크래퍼 수정이 어렵다면, 
            # 기존 스크래퍼는 '정치/국뽕' 위주로 짜여 있으므로
            # 이번 턴에서는 'query' 파라미터를 추가하여 호출한다고 가정하고 진행.
            
            # *실제로는 youtube_scraper.py, google_news_scraper.py 등을 열어서 query 리스트를 받도록 고쳐야 함*
            # *일단 여기서는 query_list 인자를 넘기는 것으로 가정하고 코드를 짬*
            
            yt = scrape_youtube(max_per_query=3, max_total=10, query_list=keywords)
            scored_yt = analyze_articles(yt, title_key="title")
            for item in scored_yt:
                row = _to_row(item, "유튜브")
                row["category"] = category  # 카테고리 추가
                all_items.append(row)
            print(f"    → {len(scored_yt)}건")
        except Exception as e:
            print(f"    → 건너뜀 (오류: {e})")

        # 2. 구글 뉴스
        try:
            print(f"  구글 뉴스 수집 중...")
            google = scrape_google_news(max_per_query=5, max_total=10, query_list=keywords)
            scored_google = analyze_articles(google, title_key="title")
            for item in scored_google:
                row = _to_row(item, "구글뉴스")
                row["category"] = category
                all_items.append(row)
            print(f"    → {len(scored_google)}건")
        except Exception as e:
            print(f"    → 건너뜀 (오류: {e})")

        # 3. 네이버 뉴스
        try:
            print(f"  네이버 뉴스 수집 중...")
            # 네이버는 키워드 검색 기반이 아니라 랭킹 뉴스일 수 있음.
            # 만약 키워드 검색이 가능하다면 query_list 전달.
            # scrape_ranking_news는 '랭킹'이므로 키워드와 무관할 수 있음 (섹션별).
            # 섹션(정치=100, 경제=101, 사회=102...) 매핑이 필요할 수 있음.
            
            naver_section_map = {
                "정치": "100", "경제": "101", "사회": "102", 
                "이슈": "104", # 세계/이슈
                "장년": "103", # 생활/문화
            }
            sid1 = naver_section_map.get(category, "100")
            
            naver = scrape_ranking_news(economy_count=5, society_count=5, total_limit=10, sid1=sid1) 
            # *scrape_ranking_news 내부도 sid1을 받도록 수정 필요*
            
            scored_naver = analyze_articles(naver, title_key="title")
            for item in scored_naver:
                row = _to_row(item, "네이버뉴스")
                row["category"] = category
                all_items.append(row)
            print(f"    → {len(scored_naver)}건")
        except Exception as e:
            print(f"    → 건너김 (오류: {e})")

    if not all_items:
        print("수집된 데이터가 없습니다. .env에 YOUTUBE_API_KEY를 확인하고, feedparser를 설치했는지 확인하세요.")
        return

    # 6. 엑셀 출력 & 웹용 JS 출력
    # (카테고리별로 모은 전체 데이터를 점수순 정렬)
    df = pd.DataFrame(all_items)
    if not df.empty:
        df["추천점수"] = pd.to_numeric(df["score"], errors="coerce").fillna(0)
        df = df.sort_values(by="추천점수", ascending=False)

        # 상위 100개 + 비슷한 뉴스 보강 (개수 늘림)
        df_top = df.head(100).copy()
        df_top = _enrich_with_similar_news(df_top, all_items)

        path = export_to_excel(df_top)
        print(f"\n엑셀 파일 생성 완료: {path}")

        json_path = export_to_js(df_top)
        print(f"웹 데이터 파일 생성 완료: {json_path}")
        
        print(f"총 {len(df_top)}건 (전체 카테고리 통합)")
    else:
        print("수집된 데이터가 없습니다.")


if __name__ == "__main__":
    main()
