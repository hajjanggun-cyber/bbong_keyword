
"""
유튜브 + 구글뉴스 + 네이버 뉴스 -> 통합 엑셀 1개 파일
"""

import os
import re
import json
import subprocess
import difflib
import sys
from datetime import datetime

# py 폴더를 모듈 경로에 추가
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "py"))

# .env 로드 (현재 디렉토리 기준)
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_dotenv(_env_path)
except ImportError:
    pass

import pandas as pd

from aggro_analyzer import analyze_articles
from excel_reporter import export_to_js
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


def _is_similar(title1: str, title2: str) -> bool:
    """두 제목이 비슷한지 (difflib 사용, 50% 이상 유사)."""
    if not title1 or not title2:
        return False
    # 간단한 정규화 (공백 제거 등)
    t1 = re.sub(r"\s+", "", str(title1))
    t2 = re.sub(r"\s+", "", str(title2))
    return difflib.SequenceMatcher(None, t1, t2).ratio() >= 0.5


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


def _load_existing_data() -> list:
    """기존 data.js에서 JSON 데이터 로드."""
    try:
        # 프로젝트 루트 기준 data.js
        root_dir = os.path.dirname(os.path.abspath(__file__))
        data_path = os.path.join(root_dir, "data.js")
        
        if not os.path.exists(data_path):
            return []
            
        with open(data_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # JS 변수 선언(var 또는 const keywordData = ) 제거하고 JSON 파싱
        # 예: var keywordData = [...];
        match = re.search(r"(?:var|const)\s+keywordData\s*=\s*(\[.*\]);", content, re.DOTALL)
        if match:
            json_str = match.group(1)
            return json.loads(json_str)
        return []
    except Exception as e:
        print(f"[경고] 기존 데이터 로드 실패: {e}")
        return []


def _collect_with_auto_expand(scraper_func, min_results=5, **kwargs):
    """
    자동 기간 확장 수집: 1일 → 3일 → 7일 → 30일
    최소 min_results개 이상 수집될 때까지 기간 확장.
    
    Args:
        scraper_func: 스크래퍼 함수 (days_back 파라미터 지원 필요)
        min_results: 최소 결과 개수 (기본 5개)
        **kwargs: 스크래퍼 함수에 전달할 추가 인자
    
    Returns:
        수집된 결과 리스트
    """
    date_ranges = [1, 3, 7, 30]  # 오늘 → 3일 → 1주 → 1개월
    
    for days_back in date_ranges:
        try:
            results = scraper_func(days_back=days_back, **kwargs)
            if len(results) >= min_results:
                if days_back > 1:
                    print(f"    (기간 확장: {days_back}일)")
                return results
        except Exception:
            continue
    
    # 모든 시도 실패 시 마지막 시도 결과 반환 (빈 리스트일 수 있음)
    try:
        return scraper_func(days_back=30, **kwargs)
    except Exception:
        return []


def run_collection(selected_category, topics_dict):
    """특정 카테고리에 대해 수집을 수행하고 데이터 리스트를 반환"""
    all_items = []
    scraper_status = {"youtube": "OK", "google": "OK", "naver": "OK"}
    
    base_keywords = topics_dict.get(selected_category, [])
    selected_keywords = base_keywords + [selected_category, f"{selected_category} 뉴스"]
    
    print(f"\n--- [{selected_category}] 수집 중... ---")
    
    # 1. 유튜브
    try:
        print(f"  유튜브 수집 중...")
        yt_results = _collect_with_auto_expand(
            scrape_youtube, 
            min_results=5, 
            query_list=selected_keywords, 
            max_results=20
        )
        scored_yt = analyze_articles(yt_results, title_key="title")
        for item in scored_yt:
            row = _to_row(item, "유튜브")
            row["카테고리"] = selected_category
            all_items.append(row)
        print(f"    → {len(scored_yt)}건")
    except Exception as e:
        print(f"    → 유튜브 건너뜀: {e}")
        scraper_status["youtube"] = f"에러: {e}"

    # 2. 구글 뉴스
    try:
        print(f"  구글 뉴스 수집 중...")
        from google_news_scraper import scrape_google_news
        google = _collect_with_auto_expand(
            scrape_google_news, 
            min_results=5, 
            query_list=selected_keywords, 
            limit=20
        )
        scored_google = analyze_articles(google, title_key="title")
        for item in scored_google:
            row = _to_row(item, "구글뉴스")
            row["카테고리"] = selected_category
            all_items.append(row)
        print(f"    → {len(scored_google)}건")
    except Exception as e:
        print(f"    → 구글 건너뜀: {e}")
        scraper_status["google"] = f"에러: {e}"

    # 3. 네이버 뉴스
    try:
        print(f"  네이버 뉴스 수집 중...")
        naver_section_map = {"정치": "100", "경제": "101", "사회": "102", "장년": "103"}
        sid1 = naver_section_map.get(selected_category, "100")
        naver = scrape_ranking_news(economy_count=5, society_count=5, total_limit=10, sid1=sid1, query_list=selected_keywords)
        scored_naver = analyze_articles(naver, title_key="title")
        for item in scored_naver:
            row = _to_row(item, "네이버뉴스")
            row["카테고리"] = selected_category
            all_items.append(row)
        print(f"    → {len(scored_naver)}건")
    except Exception as e:
        print(f"    → 네이버 건너뜀: {e}")
        scraper_status["naver"] = f"에러: {e}"
        
    return all_items, scraper_status

def main() -> None:
    from aggro_keywords import SEARCH_TOPICS
    from excel_reporter import export_to_js, _ensure_columns
    import pandas as pd

    print("\n[주제 선택]")
    print("0. 전체 수집 (정치, 경제, 사회, 장년 모두)")
    topics = list(SEARCH_TOPICS.keys())
    for i, topic in enumerate(topics):
        print(f"{i+1}. {topic}")
    
    try:
        choice = int(input("\n번호를 입력하세요 (0~4): "))
    except ValueError:
        print("숫자를 입력해주세요.")
        return

    to_collect = []
    if choice == 0:
        to_collect = topics
    elif 1 <= choice <= len(topics):
        to_collect = [topics[choice - 1]]
    else:
        print("잘못된 번호입니다.")
        return

    # 기존 데이터 로드 (누적용)
    total_existing = _load_existing_data()
    
    # 누적 결과를 담을 리스트 (이번에 수집할 카테고리들은 기존 목록에서 제거 후 새로 추가)
    final_accumulated = [item for item in total_existing if item.get("카테고리") not in to_collect]
    
    current_status = {"youtube": "OK", "google": "OK", "naver": "OK"}

    for cat in to_collect:
        new_items, status = run_collection(cat, SEARCH_TOPICS)
        final_accumulated.extend(new_items)
        # 상태 업데이트
        for k, v in status.items():
            if v != "OK": current_status[k] = v

    if not final_accumulated:
        print("표시할 데이터가 없습니다.")
        return

    # 데이터 정규화 및 저장
    df_final = pd.DataFrame(final_accumulated)
    json_path = export_to_js(df_final, scraper_status=current_status)
    print(f"\n[성공] 웹 데이터 업데이트 완료: {json_path}")
    print(f"[정보] 총 {len(df_final)}건의 데이터가 저장되었습니다.")

    # 7. 깃허브 자동 푸시
    git_push()


def git_push():
    """데이터 생성 후 깃허브에 자동 푸시"""
    print("\n[Git] 깃허브 자동 푸시 시작...")
    try:
        # 프로젝트 루트로 이동 (현재 파일이 루트에 있음)
        root_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 1. git add
        subprocess.run(["git", "add", "."], cwd=root_dir, check=True)
        
        # 2. git commit
        # 변경사항이 없으면 에러가 날 수 있으므로 check=False로 하고 출력만 확인하거나
        # status를 먼저 체크할 수도 있음. 여기서는 간단히 try로 감쌈.
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        commit_msg = f"Auto: Update data files ({current_time})"
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=root_dir, check=False)
        
        # 3. git push
        subprocess.run(["git", "push", "origin", "main"], cwd=root_dir, check=True)
        print("[Git] 푸시 완료!")
        
    except Exception as e:
        print(f"[Git] 푸시 실패: {e}")



if __name__ == "__main__":
    main()
