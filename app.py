# 정세담 정책 프로그램 - 단일 파일 버전 (Streamlit Cloud 호환)
# modules, config 없이 모든 기능 통합

import streamlit as st
import os
import json
import sqlite3
import base64
from datetime import datetime, date
from io import BytesIO
from typing import Dict, Any, Optional, List, Tuple
from contextlib import contextmanager
from zipfile import ZipFile
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# OpenAI import
try:
    from openai import OpenAI
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key and hasattr(st, 'secrets'):
        api_key = st.secrets.get("OPENAI_API_KEY", "")
    if not api_key:
        st.error("⚠️ OPENAI_API_KEY가 설정되지 않았습니다. Streamlit Cloud Secrets에서 설정하세요.")
        st.stop()
    client = OpenAI(api_key=api_key)
except Exception as e:
    st.error(f"OpenAI 라이브러리 로드 실패: {e}")
    st.stop()

# PIL import
try:
    from PIL import Image
except:
    st.error("Pillow 라이브러리가 필요합니다. requirements.txt에 pillow>=10.0.0 추가하세요.")
    st.stop()

# ReportLab import
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
except:
    st.error("ReportLab 라이브러리가 필요합니다. requirements.txt에 reportlab>=4.0.0 추가하세요.")
    st.stop()

# ==================== 설정 (Settings) ====================

DB_PATH = "data/policies.db"

TARGET_AUDIENCES = {
    "시민": {
        "tone": "친근하고 이해하기 쉬운",
        "focus": "일상 생활 혜택, 실생활 변화"
    },
    "청년": {
        "tone": "트렌디하고 직관적인",
        "focus": "기회 확대, 미래 전망"
    },
    "노인": {
        "tone": "친절하고 따뜻한",
        "focus": "안전, 편의성, 접근성"
    },
    "학부모": {
        "tone": "신뢰감 있고 구체적인",
        "focus": "자녀 안전, 교육 효과"
    },
    "기업": {
        "tone": "전문적이고 효율적인",
        "focus": "비용 절감, 규제 완화, ROI"
    },
    "지자체 공무원": {
        "tone": "체계적이고 실무적인",
        "focus": "실행 가능성, 예산, 법적 근거"
    },
    "의회/의원": {
        "tone": "설득적이고 근거 중심",
        "focus": "정책 효과, 국민 체감, 성과 지표"
    }
}

VIDEO_PLATFORMS = {
    "Sora": "https://sora.openai.com",
    "Runway": "https://runwayml.com",
    "Pika": "https://pika.art",
    "Luma Dream Machine": "https://lumalabs.ai"
}

IMAGE_SIZES = ["1024x1024", "1024x1792", "1792x1024"]
VIDEO_DURATIONS = ["10초", "20초", "30초", "60초"]

CONTENT_PACKAGES = {
    "A 마케팅": ["이미지 2장", "영상 1개", "홍보 문구 3종"],
    "B 정책 설명": ["정책 요약", "PPT 구성", "FAQ"],
    "C 풀 패키지": ["이미지 4장", "영상 2개", "홍보 문구 5종", "정책 문서", "PPT", "성과 지표"]
}

DEFAULT_IMAGE_STYLE = """
Professional documentary photography, ultra-realistic, photojournalistic style.
Location: Modern South Korea (Seoul, Busan, or other major Korean cities).
Architecture: Contemporary Korean buildings, clean streets, realistic urban/suburban settings.
People: Natural Korean faces with accurate facial features, realistic expressions.
DO NOT distort faces - maintain natural human proportions and features.
Lighting: Natural daylight, soft shadows, professional photography lighting.
Color palette: Natural, slightly desaturated, clean and modern aesthetic.
Atmosphere: Authentic everyday Korean life, genuine moments.
Technical requirements:
- High resolution, sharp focus on main subjects
- Proper depth of field
- Realistic skin tones (Korean complexion)
- Natural body proportions
- Clear, undistorted facial features
- Professional color grading
Forbidden elements:
- NO text, logos, signs with readable text
- NO distorted or warped faces
- NO unrealistic proportions
- NO stock photo feel
- NO overly posed or artificial scenes
- NO generic Asian stereotypes
Style reference: Korean documentary photography, modern Korean cinema aesthetics.
"""

# ==================== 데이터베이스 (Database) ====================

@contextmanager
def get_db():
    # data 폴더가 없으면 생성
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_database():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                target_audience TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'draft',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS policy_contents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_id INTEGER NOT NULL,
                content_type TEXT NOT NULL,
                content_data TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (policy_id) REFERENCES policies(id)
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS policy_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_id INTEGER NOT NULL,
                view_count INTEGER DEFAULT 0,
                engagement_score REAL DEFAULT 0.0,
                feedback_data TEXT,
                metrics_data TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (policy_id) REFERENCES policies(id)
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS generated_media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_id INTEGER NOT NULL,
                media_type TEXT NOT NULL,
                media_url TEXT,
                media_data BLOB,
                prompt TEXT,
                generation_params TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (policy_id) REFERENCES policies(id)
            )
        """)
        
        conn.commit()

def create_policy(title: str, category: str, target_audience: str, description: str = "") -> int:
    now = datetime.now().isoformat()
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO policies (title, category, target_audience, description, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'draft', ?, ?)
        """, (title, category, target_audience, description, now, now))
        conn.commit()
        return cursor.lastrowid

def update_policy_status(policy_id: int, status: str):
    now = datetime.now().isoformat()
    with get_db() as conn:
        conn.execute("""
            UPDATE policies SET status = ?, updated_at = ? WHERE id = ?
        """, (status, now, policy_id))
        conn.commit()

def save_policy_content(policy_id: int, content_type: str, content_data: Dict[str, Any], metadata: Optional[Dict] = None):
    now = datetime.now().isoformat()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO policy_contents (policy_id, content_type, content_data, metadata, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            policy_id,
            content_type,
            json.dumps(content_data, ensure_ascii=False),
            json.dumps(metadata or {}, ensure_ascii=False),
            now
        ))
        conn.commit()

def save_generated_media(policy_id: int, media_type: str, media_data: bytes, prompt: str, params: Dict[str, Any]):
    now = datetime.now().isoformat()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO generated_media (policy_id, media_type, media_data, prompt, generation_params, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            policy_id,
            media_type,
            media_data,
            prompt,
            json.dumps(params, ensure_ascii=False),
            now
        ))
        conn.commit()

def get_policy(policy_id: int) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM policies WHERE id = ?", (policy_id,)).fetchone()
        if row:
            return dict(row)
        return None

def get_all_policies(limit: int = 50) -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM policies ORDER BY created_at DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]

def get_policy_contents(policy_id: int) -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM policy_contents WHERE policy_id = ? ORDER BY created_at DESC
        """, (policy_id,)).fetchall()
        results = []
        for row in rows:
            data = dict(row)
            data['content_data'] = json.loads(data['content_data'])
            data['metadata'] = json.loads(data['metadata']) if data['metadata'] else {}
            results.append(data)
        return results

def get_generated_media(policy_id: int, media_type: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_db() as conn:
        if media_type:
            rows = conn.execute("""
                SELECT * FROM generated_media WHERE policy_id = ? AND media_type = ? ORDER BY created_at DESC
            """, (policy_id, media_type)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM generated_media WHERE policy_id = ? ORDER BY created_at DESC
            """, (policy_id,)).fetchall()
        
        results = []
        for row in rows:
            data = dict(row)
            data['generation_params'] = json.loads(data['generation_params']) if data['generation_params'] else {}
            results.append(data)
        return results

def get_policies_by_date(date_str: str) -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM policies 
            WHERE date(created_at) = date(?)
            ORDER BY created_at DESC
        """, (date_str,)).fetchall()
        return [dict(row) for row in rows]

def get_policies_by_date_range(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM policies 
            WHERE date(created_at) BETWEEN date(?) AND date(?)
            ORDER BY created_at DESC
        """, (start_date, end_date)).fetchall()
        return [dict(row) for row in rows]

# ==================== AI 엔진 (AI Engine) ====================

def parse_json_response(text: str) -> Optional[Dict]:
    text = text.strip()
    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except:
        return None

def generate_policy_analysis(
    title: str,
    category: str,
    target_audience: str,
    description: str,
    keywords: str = "",
    constraints: str = "",
    model: str = "gpt-4o"
) -> Tuple[Optional[Dict], str]:
    
    prompt = f"""
당신은 정세담 정책 자동화 시스템의 AI입니다.
정책의 기획부터 실행, 홍보, 성과관리까지 전체 프로세스를 설계합니다.

[입력 정보]
정책 제목: {title}
정책 카테고리: {category}
대상: {target_audience}
정책 설명: {description}
강조 키워드: {keywords}
제약 조건: {constraints}

[출력 규칙]
- 반드시 JSON 형식으로만 출력
- 한국 현실에 맞는 실행 가능한 내용
- 과장 금지, 측정 가능한 지표 사용
- 대상에 맞는 톤과 메시지

[JSON 스키마]
{{
  "policy_planning": {{
    "objective": "정책 목표 (3-5문장)",
    "target_analysis": "대상 분석 (니즈, 특성, 접근법 3-5문장)",
    "key_strategies": ["핵심 전략 5-8개"],
    "expected_outcomes": ["기대 효과 5-7개"],
    "timeline": {{
      "preparation": "준비 단계 내용",
      "pilot": "시범 운영 내용",
      "expansion": "확대 적용 내용"
    }}
  }},
  
  "execution_plan": {{
    "action_items": [
      {{
        "phase": "단계명",
        "action": "실행 내용",
        "responsible": "담당 주체",
        "timeline": "소요 기간"
      }}
    ],
    "resources_needed": {{
      "budget_range": "예산 범위 (구체적 금액 대신 범주)",
      "personnel": "필요 인력",
      "infrastructure": "필요 인프라"
    }},
    "risk_management": [
      {{
        "risk": "리스크 항목",
        "impact": "영향도",
        "mitigation": "완화 방안"
      }}
    ]
  }},
  
  "communication_strategy": {{
    "key_messages": ["핵심 메시지 5-8개"],
    "channels": [
      {{
        "channel": "채널명",
        "content_type": "콘텐츠 형식",
        "frequency": "발행 주기"
      }}
    ],
    "target_specific_messages": {{
      "citizens": "시민 대상 메시지",
      "youth": "청년 대상 메시지",
      "elderly": "노인 대상 메시지",
      "parents": "학부모 대상 메시지"
    }}
  }},
  
  "content_briefs": {{
    "image_brief_1": {{
      "concept": "이미지 컨셉 (5-7문장)",
      "scene_description": "장면 상세 묘사 (10-15문장)",
      "visual_style": "비주얼 스타일 (촬영 기법, 조명, 색감)",
      "key_message": "전달할 핵심 메시지"
    }},
    "image_brief_2": {{
      "concept": "이미지 컨셉 (5-7문장)",
      "scene_description": "장면 상세 묘사 (10-15문장)",
      "visual_style": "비주얼 스타일 (촬영 기법, 조명, 색감)",
      "key_message": "전달할 핵심 메시지"
    }},
    "video_brief": {{
      "duration": "영상 길이",
      "narrative_arc": "스토리 구조 (5-8문장)",
      "scenes": [
        {{
          "timestamp": "시간대",
          "scene": "장면 내용",
          "visuals": "비주얼 요소",
          "audio": "오디오 (내레이션/음악/효과음)",
          "message": "전달 메시지"
        }}
      ],
      "style_guide": "영상 스타일 가이드",
      "call_to_action": "행동 유도 문구"
    }}
  }},
  
  "marketing_materials": {{
    "slogan": "슬로건 (20-30자)",
    "tagline": "태그라인 (40-60자)",
    "elevator_pitch": "엘리베이터 피치 (150-200자)",
    "press_release": "보도자료 형식 (300-500자)",
    "social_media_posts": [
      {{
        "platform": "플랫폼",
        "content": "게시물 내용",
        "hashtags": ["해시태그"]
      }}
    ],
    "faq": [
      {{
        "question": "자주 묻는 질문",
        "answer": "답변"
      }}
    ]
  }},
  
  "performance_metrics": {{
    "kpi_framework": [
      {{
        "category": "지표 카테고리",
        "metric": "측정 항목",
        "measurement_method": "측정 방법",
        "target_range": "목표 범위 (구간/추이)",
        "data_source": "데이터 출처"
      }}
    ],
    "success_criteria": ["성공 기준 5-7개"],
    "monitoring_plan": {{
      "daily": "일간 모니터링 항목",
      "weekly": "주간 모니터링 항목",
      "monthly": "월간 모니터링 항목"
    }},
    "improvement_triggers": ["개선이 필요한 시점을 알리는 지표 5-7개"]
  }},
  
  "stakeholder_management": {{
    "stakeholders": [
      {{
        "group": "이해관계자 그룹",
        "interests": "관심사",
        "engagement_strategy": "소통 전략"
      }}
    ],
    "objection_handling": [
      {{
        "objection": "예상 반대 의견",
        "response": "대응 논리"
      }}
    ]
  }}
}}

위 스키마를 정확히 따라 JSON만 출력하세요.
"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "당신은 정책 전문가입니다. 항상 JSON 형식으로만 응답합니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4000
        )
        
        raw_text = response.choices[0].message.content
        parsed_data = parse_json_response(raw_text)
        
        if parsed_data:
            return parsed_data, raw_text
        
        # JSON 파싱 실패시 재시도
        retry_prompt = f"""
이전 응답이 올바른 JSON 형식이 아닙니다.
아래 내용을 완벽한 JSON으로 다시 출력해주세요.

{raw_text}
"""
        
        retry_response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "JSON 형식으로만 응답합니다."},
                {"role": "user", "content": retry_prompt}
            ],
            temperature=0.3,
            max_tokens=4000
        )
        
        retry_text = retry_response.choices[0].message.content
        retry_parsed = parse_json_response(retry_text)
        
        return retry_parsed, retry_text
        
    except Exception as e:
        return None, f"Error: {str(e)}"

def generate_image_prompt(brief: Dict[str, Any], style_override: str = "") -> str:
    concept = brief.get("concept", "")
    scene = brief.get("scene_description", "")
    style = brief.get("visual_style", "")
    message = brief.get("key_message", "")
    
    base_style = style_override if style_override else DEFAULT_IMAGE_STYLE
    
    prompt = f"""
{concept}

Scene description: {scene}

Visual style: {style}

{base_style}

Key message to convey: {message}

Important: Create realistic Korean people with natural, undistorted facial features.
No text or writing should appear anywhere in the image.
Focus on authentic Korean urban/suburban environment and genuine human expressions.
"""
    
    return prompt.strip()

def generate_video_prompts_3styles(brief: Dict[str, Any]) -> Dict[str, str]:
    """10초 영상 3가지 스타일 프롬프트 생성"""
    
    narrative = brief.get("narrative_arc", "")
    cta = brief.get("call_to_action", "")
    
    base_context = f"""
Duration: 10 seconds
Location: Modern South Korea
Language: Korean subtitles only
No English text visible
"""
    
    # 스타일 1: 다큐멘터리
    style1 = f"""
[스타일 1: 다큐멘터리 리얼리즘]

{base_context}

Visual Style:
- Handheld camera feel, natural movements
- Realistic lighting, documentary aesthetic
- Authentic Korean street scenes and people
- Observational approach, fly-on-the-wall style
- Natural color grading with slight desaturation

Camera:
- Medium shots and close-ups
- Slight camera shake for realism
- Follow subjects naturally

Audio:
- Natural ambient sounds (traffic, voices, city sounds)
- Minimal background music
- Natural Korean dialogue or voice-over

Narrative: {narrative}

Mood: Authentic, grounded, trustworthy
Pacing: Steady, observational
Final Message: {cta}

Technical: 24fps, cinematic aspect ratio, professional documentary style
"""
    
    # 스타일 2: 시네마틱
    style2 = f"""
[스타일 2: 시네마틱 드라마]

{base_context}

Visual Style:
- Smooth cinematic camera movements (gimbal/slider)
- Dramatic lighting with warm and cool tones
- Korean urban landscape with cinematic composition
- Establishing shots of Seoul skyline or modern architecture
- Rich color grading inspired by Korean cinema

Camera:
- Wide establishing shots
- Slow push-ins and reveals
- Overhead/drone shots of Korean cityscape
- Smooth tracking shots

Audio:
- Emotional background music (orchestral or modern Korean OST style)
- Carefully designed sound effects
- Polished voice-over narration

Narrative: {narrative}

Mood: Inspiring, emotional, aspirational
Pacing: Dynamic with emotional beats
Final Message: {cta}

Technical: 24fps, anamorphic feel, cinematic color grade
"""
    
    # 스타일 3: 모던 다이내믹
    style3 = f"""
[스타일 3: 모던 다이내믹]

{base_context}

Visual Style:
- Fast-paced dynamic cuts
- Modern Korean lifestyle and technology
- Bright, energetic visuals
- Clean, contemporary aesthetic
- Vibrant color grading with saturated tones

Camera:
- Quick cuts between multiple angles
- Time-lapse of Korean city life
- Dynamic camera movements
- Close-ups on details and faces
- Match cuts for visual rhythm

Audio:
- Upbeat modern Korean music
- Rhythmic sound design
- Quick voice-over or on-screen Korean text animations
- Sync with visual cuts

Narrative: {narrative}

Mood: Energetic, modern, forward-thinking
Pacing: Fast, rhythmic, attention-grabbing
Final Message: {cta}

Technical: 30fps or 60fps slow-motion elements, high contrast, vibrant colors
"""
    
    return {
        "documentary": style1,
        "cinematic": style2,
        "modern_dynamic": style3
    }

# ==================== 이미지 생성 (Image Generator) ====================

def generate_policy_image(
    brief: dict,
    size: str = "1024x1024",
    quality: str = "standard"
) -> Optional[Tuple[Image.Image, bytes]]:
    """정책 이미지 생성 (brief 기반)"""
    
    prompt = generate_image_prompt(brief)
    
    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=size,
            quality=quality,
            n=1,
            response_format="b64_json"
        )
        
        if response.data and len(response.data) > 0:
            b64_data = response.data[0].b64_json
            image_bytes = base64.b64decode(b64_data)
            image = Image.open(BytesIO(image_bytes))
            return (image, image_bytes)
        
        return None
        
    except Exception as e:
        st.error(f"이미지 생성 실패: {str(e)}")
        return None

def batch_generate_images(prompts: List[str], size: str = "1024x1024", quality: str = "standard") -> List[Tuple[Image.Image, bytes]]:
    """여러 이미지 순차 생성"""
    results = []
    for prompt in prompts:
        try:
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=size,
                quality=quality,
                n=1,
                response_format="b64_json"
            )
            
            if response.data and len(response.data) > 0:
                b64_data = response.data[0].b64_json
                image_bytes = base64.b64decode(b64_data)
                image = Image.open(BytesIO(image_bytes))
                results.append((image, image_bytes))
        except Exception as e:
            st.error(f"이미지 생성 실패: {str(e)}")
            continue
    
    return results

# ==================== PDF/ZIP 내보내기 (Export Manager) ====================

def create_pdf_report(policy: Dict[str, Any], analysis: Dict[str, Any]) -> bytes:
    """한글 정책 보고서 PDF 생성"""
    
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # 한글 폰트 등록
    try:
        pdfmetrics.registerFont(UnicodeCIDFont('HYSMyeongJo-Medium'))
        font_name = 'HYSMyeongJo-Medium'
    except:
        font_name = 'Helvetica'
    
    # 제목
    c.setFont(font_name, 20)
    c.drawString(50, height - 50, "정책 보고서")
    
    c.setFont(font_name, 14)
    c.drawString(50, height - 80, f"제목: {policy['title']}")
    c.drawString(50, height - 100, f"카테고리: {policy['category']}")
    c.drawString(50, height - 120, f"대상: {policy['target_audience']}")
    
    c.setFont(font_name, 10)
    y_position = height - 160
    
    # 정책 설명
    if policy.get('description'):
        c.drawString(50, y_position, "정책 설명:")
        y_position -= 20
        desc_lines = policy['description'][:200].split('\n')
        for line in desc_lines[:5]:
            c.drawString(60, y_position, line[:80])
            y_position -= 15
    
    c.showPage()
    c.save()
    
    buffer.seek(0)
    return buffer.read()

def create_zip_export(
    policy: Dict[str, Any],
    analysis: Dict[str, Any],
    images: List[bytes] = None,
    video_prompts: List[str] = None
) -> bytes:
    """모든 자료를 ZIP으로 압축"""
    
    buffer = BytesIO()
    
    with ZipFile(buffer, 'w') as zipf:
        # 정책 정보
        zipf.writestr("policy_info.json", json.dumps(policy, ensure_ascii=False, indent=2))
        
        # AI 분석 결과
        zipf.writestr("analysis_full.json", json.dumps(analysis, ensure_ascii=False, indent=2))
        
        # 이미지
        if images:
            for idx, img_bytes in enumerate(images, 1):
                zipf.writestr(f"images/image_{idx}.png", img_bytes)
        
        # 영상 프롬프트
        if video_prompts:
            for idx, prompt in enumerate(video_prompts, 1):
                zipf.writestr(f"video_prompts/prompt_{idx}.txt", prompt)
        
        # README
        readme = f"""
정세담 정책 프로그램 - 결과물 패키지

정책 제목: {policy['title']}
생성일: {policy['created_at']}

포함 내용:
- policy_info.json: 정책 기본 정보
- analysis_full.json: AI 분석 전체 결과
- images/: 생성된 이미지
- video_prompts/: 영상 제작 프롬프트

사용 방법:
1. analysis_full.json을 열어 전체 분석 내용 확인
2. images 폴더의 이미지 활용
3. video_prompts의 프롬프트를 Runway, Pika 등에 입력
"""
        zipf.writestr("README.txt", readme)
    
    buffer.seek(0)
    return buffer.read()

# ==================== Streamlit UI ====================

st.set_page_config(
    page_title="정세담 정책 프로그램",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

def init_session_state():
    defaults = {
        "current_policy_id": None,
        "current_analysis": None,
        "generated_images": [],
        "video_prompts_3styles": [],
        "workflow_step": "기획",
        "show_results": False,
        "selected_category": "",
        "temp_selection": ""
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()
init_database()

st.markdown('<div class="main-header">🏛️ 정세담 정책 프로그램</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">정책 기획·실행·홍보·성과관리 자동화 시스템</div>', unsafe_allow_html=True)

# 사이드바
with st.sidebar:
    st.markdown("### 📋 프로세스 단계")
    
    steps = ["기획", "실행", "홍보", "성과관리"]
    current_step_idx = steps.index(st.session_state.workflow_step)
    
    for idx, step in enumerate(steps):
        if idx < current_step_idx:
            st.success(f"✅ {step}")
        elif idx == current_step_idx:
            st.info(f"▶️ {step} (현재)")
        else:
            st.write(f"⏸️ {step}")
    
    st.divider()
    
    st.markdown("### 📅 날짜별 정책 검색")
    
    search_type = st.radio("검색 방식", ["전체 보기", "날짜 선택", "날짜 범위"], horizontal=True)
    
    if search_type == "날짜 선택":
        selected_date = st.date_input("날짜 선택", value=date.today())
        policies = get_policies_by_date(selected_date.strftime("%Y-%m-%d"))
        st.caption(f"{selected_date.strftime('%Y-%m-%d')} 정책 {len(policies)}건")
    elif search_type == "날짜 범위":
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("시작", value=date.today())
        with col2:
            end_date = st.date_input("종료", value=date.today())
        policies = get_policies_by_date_range(
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d")
        )
        st.caption(f"{len(policies)}건 발견")
    else:
        policies = get_all_policies(limit=20)
        st.caption(f"최근 {len(policies)}건")
    
    st.markdown("### 🗂️ 저장된 정책")
    
    if policies:
        for policy in policies:
            with st.expander(f"{policy['title'][:20]}..."):
                st.write(f"📅 {policy['created_at'][:10]}")
                st.write(f"카테고리: {policy['category']}")
                st.write(f"대상: {policy['target_audience']}")
                if st.button("불러오기", key=f"load_{policy['id']}"):
                    st.session_state.current_policy_id = policy['id']
                    contents = get_policy_contents(policy['id'])
                    if contents:
                        for content in contents:
                            if content['content_type'] == 'analysis':
                                st.session_state.current_analysis = content['content_data']
                    
                    media = get_generated_media(policy['id'])
                    st.session_state.generated_images = []
                    
                    for m in media:
                        if m['media_type'] == 'image' and m['media_data']:
                            img = Image.open(BytesIO(m['media_data']))
                            st.session_state.generated_images.append({
                                "image": img,
                                "bytes": m['media_data'],
                                "brief": "loaded"
                            })
                    
                    st.success(f"✅ 정책 불러오기 완료!")
                    st.rerun()
    else:
        st.info("저장된 정책이 없습니다")
    
    st.divider()
    
    if st.button("🆕 새 정책 시작", use_container_width=True):
        for key in ["current_policy_id", "current_analysis", "generated_images", "video_prompts_3styles", "selected_category", "temp_selection"]:
            st.session_state[key] = [] if "images" in key or "prompts" in key else ("" if "category" in key or "selection" in key else None)
        st.session_state.workflow_step = "기획"
        st.session_state.show_results = False
        st.rerun()

# 메인 탭
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📝 정책 입력",
    "🤖 AI 분석 생성",
    "🖼️ 이미지 생성",
    "🎬 영상 프롬프트",
    "📊 결과 및 내보내기"
])

with tab1:
    st.markdown("### 1️⃣ 정책 기본 정보 입력")
    
    col1, col2 = st.columns(2)
    
    with col1:
        policy_title = st.text_input(
            "정책 제목 *",
            placeholder="예: 도시 대기질 실시간 관리 정책",
            help="정책의 핵심을 담은 명확한 제목"
        )
        
        # 카테고리 데이터베이스
        category_database = {
            "환경": {
                "대기질": ["미세먼지 저감", "대기오염 관리", "실시간 모니터링", "배출가스 규제"],
                "수질": ["하천 정화", "상수도 개선", "하수처리", "수질 모니터링"],
                "폐기물": ["쓰레기 감량", "재활용", "음식물쓰레기", "일회용품 규제"],
                "에너지": ["신재생에너지", "태양광", "풍력", "에너지 효율화", "절전"],
                "기후변화": ["탄소중립", "온실가스 감축", "기후 적응", "ESG"]
            },
            "교통": {
                "대중교통": ["버스 노선 개편", "지하철 확충", "환승 편의", "요금 정책"],
                "주차": ["공영주차장", "주차난 해소", "불법주차 단속", "공유주차"],
                "보행": ["보행자 우선", "보행로 확충", "횡단보도 개선", "무장애 도로"],
                "자전거": ["자전거 도로", "공유자전거", "자전거 주차장", "안전 인프라"]
            },
            "복지": {
                "노인복지": ["경로당 지원", "돌봄 서비스", "일자리 창출", "건강관리", "치매 예방"],
                "아동복지": ["보육 지원", "놀이터 확충", "아동학대 예방", "방과후 돌봄"],
                "청년복지": ["주거 지원", "취업 지원", "청년수당", "창업 지원"]
            },
            "교육": {
                "학교교육": ["교육과정 개선", "학교시설 현대화", "무상급식", "돌봄교실"],
                "평생교육": ["성인 교육", "직업훈련", "온라인 강좌", "학습 지원"]
            },
            "안전": {
                "재난안전": ["화재 예방", "지진 대비", "태풍 대비", "재난 대응 훈련"],
                "범죄예방": ["CCTV 확충", "안심귀가", "학교폭력 예방", "성범죄 예방"]
            },
            "경제": {
                "일자리": ["일자리 창출", "구직 지원", "직업 훈련", "고용 안정"],
                "창업": ["창업 교육", "자금 지원", "멘토링", "공유 오피스"]
            }
        }
        
        # 선택 버튼이 눌렸을 때
        if "temp_selection" in st.session_state and st.session_state.temp_selection:
            st.session_state.selected_category = st.session_state.temp_selection
            st.session_state.temp_selection = ""
        
        # 정책 카테고리 입력창
        policy_category = st.text_input(
            "정책 카테고리 *",
            value=st.session_state.selected_category if st.session_state.selected_category else "",
            placeholder="예: 화재, 청년, 주차 등 입력하면 자동완성됩니다",
            help="한 글자씩 입력하면 관련 카테고리가 자동으로 추천됩니다"
        )
        
        # 사용자가 직접 입력하면 업데이트
        if policy_category != st.session_state.selected_category:
            st.session_state.selected_category = policy_category
        
        # 실시간 자동완성
        if policy_category and len(policy_category) > 0:
            autocomplete_suggestions = []
            
            for main_cat, sub_cats in category_database.items():
                for sub_cat, items in sub_cats.items():
                    for item in items:
                        full_path = f"{main_cat} > {sub_cat} > {item}"
                        if policy_category.lower() in full_path.lower():
                            autocomplete_suggestions.append(full_path)
            
            if autocomplete_suggestions:
                st.markdown("##### 💡 자동완성 추천")
                st.caption(f"{len(autocomplete_suggestions)}개 항목 발견 (최대 10개 표시)")
                
                for idx, suggestion in enumerate(autocomplete_suggestions[:10]):
                    cols = st.columns([5, 1])
                    with cols[0]:
                        st.markdown(f"✨ {suggestion}")
                    with cols[1]:
                        if st.button("선택", key=f"autocomplete_{idx}", use_container_width=True):
                            st.session_state.temp_selection = suggestion
                            st.rerun()
                
                if len(autocomplete_suggestions) > 10:
                    st.caption(f"+ {len(autocomplete_suggestions) - 10}개 더 있습니다.")
        
        target_audience = st.selectbox(
            "주요 대상 *",
            options=list(TARGET_AUDIENCES.keys()),
            help="정책의 주요 대상 그룹"
        )
        
        if target_audience in TARGET_AUDIENCES:
            audience_info = TARGET_AUDIENCES[target_audience]
            st.info(f"**톤**: {audience_info['tone']}\n\n**초점**: {audience_info['focus']}")
    
    with col2:
        policy_description = st.text_area(
            "정책 설명 *",
            height=150,
            placeholder="정책의 배경, 목적, 기대 효과 등을 자세히 입력하세요"
        )
        
        keywords = st.text_input(
            "강조 키워드 (쉼표로 구분)",
            placeholder="예: 시민참여, 데이터기반, 지속가능성"
        )
        
        constraints = st.text_area(
            "제약 조건 (선택)",
            height=100,
            placeholder="예: 예산 1억 이내, 3개월 시범운영"
        )
    
    content_package = st.selectbox(
        "콘텐츠 패키지",
        options=list(CONTENT_PACKAGES.keys())
    )
    
    st.info(f"**선택한 패키지 포함 항목**: {', '.join(CONTENT_PACKAGES[content_package])}")
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        if st.button("💾 정책 저장", use_container_width=True):
            if not policy_title or not policy_description:
                st.error("정책 제목과 설명은 필수입니다")
            else:
                policy_id = create_policy(
                    title=policy_title,
                    category=policy_category,
                    target_audience=target_audience,
                    description=policy_description
                )
                st.session_state.current_policy_id = policy_id
                st.success(f"✅ 정책이 저장되었습니다 (ID: {policy_id})")
                st.session_state.workflow_step = "실행"
    
    with col2:
        if st.button("🚀 AI 분석 생성", use_container_width=True):
            if not policy_title or not policy_description:
                st.error("정책 제목과 설명은 필수입니다")
            else:
                try:
                    if not st.session_state.current_policy_id:
                        policy_id = create_policy(
                            title=policy_title,
                            category=policy_category,
                            target_audience=target_audience,
                            description=policy_description
                        )
                        st.session_state.current_policy_id = policy_id
                    
                    with st.spinner("AI가 정책을 분석하고 있습니다... (30-60초 소요)"):
                        analysis, raw = generate_policy_analysis(
                            title=policy_title,
                            category=policy_category,
                            target_audience=target_audience,
                            description=policy_description,
                            keywords=keywords,
                            constraints=constraints
                        )
                        
                        if analysis:
                            st.session_state.current_analysis = analysis
                            save_policy_content(
                                st.session_state.current_policy_id,
                                "analysis",
                                analysis
                            )
                            st.success("✅ AI 분석이 완료되었습니다!")
                            st.session_state.show_results = True
                            st.session_state.workflow_step = "홍보"
                            st.balloons()
                        else:
                            st.error(f"AI 분석 생성에 실패했습니다.")
                            
                except Exception as e:
                    st.error(f"오류 발생: {str(e)}")

with tab2:
    st.markdown("### 2️⃣ AI 생성 결과")
    
    if st.session_state.current_analysis:
        analysis = st.session_state.current_analysis
        
        with st.expander("📋 정책 기획", expanded=True):
            if "policy_planning" in analysis:
                planning = analysis["policy_planning"]
                st.markdown(f"**목표**: {planning.get('objective', '')}")
                st.markdown(f"**대상 분석**: {planning.get('target_analysis', '')}")
                
                st.markdown("**핵심 전략**:")
                for idx, strategy in enumerate(planning.get("key_strategies", []), 1):
                    st.write(f"{idx}. {strategy}")
        
        with st.expander("⚙️ 실행 계획"):
            if "execution_plan" in analysis:
                execution = analysis["execution_plan"]
                
                action_items = execution.get("action_items", [])
                if action_items:
                    st.markdown("**실행 항목**:")
                    for item in action_items:
                        st.markdown(f"""
**{item.get('phase', '')}**
- 실행 내용: {item.get('action', '')}
- 담당: {item.get('responsible', '')}
- 기간: {item.get('timeline', '')}
""")
        
        with st.expander("📣 커뮤니케이션 전략"):
            if "communication_strategy" in analysis:
                comm = analysis["communication_strategy"]
                
                st.markdown("**핵심 메시지**:")
                for msg in comm.get("key_messages", []):
                    st.write(f"• {msg}")
        
        with st.expander("🎨 콘텐츠 제작 브리프"):
            if "content_briefs" in analysis:
                briefs = analysis["content_briefs"]
                
                st.markdown("### 이미지 브리프 1")
                if "image_brief_1" in briefs:
                    brief1 = briefs["image_brief_1"]
                    st.write(f"**컨셉**: {brief1.get('concept', '')}")
                    st.write(f"**장면**: {brief1.get('scene_description', '')}")
                
                st.markdown("### 이미지 브리프 2")
                if "image_brief_2" in briefs:
                    brief2 = briefs["image_brief_2"]
                    st.write(f"**컨셉**: {brief2.get('concept', '')}")
                    st.write(f"**장면**: {brief2.get('scene_description', '')}")
    
    else:
        st.info("먼저 '정책 입력' 탭에서 정책 정보를 입력하고 AI 분석을 생성해주세요.")

with tab3:
    st.markdown("### 3️⃣ 이미지 자동 생성")
    
    if st.session_state.current_analysis and "content_briefs" in st.session_state.current_analysis:
        briefs = st.session_state.current_analysis["content_briefs"]
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            image_size = st.selectbox("이미지 크기", IMAGE_SIZES)
        
        with col2:
            image_quality = st.selectbox("품질", ["standard", "hd"])
        
        with col3:
            num_images = st.number_input("생성 개수", min_value=1, max_value=4, value=2)
        
        st.divider()
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🖼️ 이미지 1 생성", use_container_width=True):
                if "image_brief_1" in briefs:
                    with st.spinner("이미지를 생성하고 있습니다... (20-40초)"):
                        result = generate_policy_image(
                            briefs["image_brief_1"],
                            size=image_size,
                            quality=image_quality
                        )
                        if result:
                            img, img_bytes = result
                            st.session_state.generated_images.append({
                                "image": img,
                                "bytes": img_bytes,
                                "brief": "image_brief_1"
                            })
                            
                            if st.session_state.current_policy_id:
                                save_generated_media(
                                    st.session_state.current_policy_id,
                                    "image",
                                    img_bytes,
                                    generate_image_prompt(briefs["image_brief_1"]),
                                    {"size": image_size, "quality": image_quality}
                                )
                            
                            st.success("✅ 이미지 1 생성 완료!")
                            st.rerun()
                        else:
                            st.error("이미지 생성에 실패했습니다")
        
        with col2:
            if st.button("🖼️ 이미지 2 생성", use_container_width=True):
                if "image_brief_2" in briefs:
                    with st.spinner("이미지를 생성하고 있습니다... (20-40초)"):
                        result = generate_policy_image(
                            briefs["image_brief_2"],
                            size=image_size,
                            quality=image_quality
                        )
                        if result:
                            img, img_bytes = result
                            st.session_state.generated_images.append({
                                "image": img,
                                "bytes": img_bytes,
                                "brief": "image_brief_2"
                            })
                            
                            if st.session_state.current_policy_id:
                                save_generated_media(
                                    st.session_state.current_policy_id,
                                    "image",
                                    img_bytes,
                                    generate_image_prompt(briefs["image_brief_2"]),
                                    {"size": image_size, "quality": image_quality}
                                )
                            
                            st.success("✅ 이미지 2 생성 완료!")
                            st.rerun()
                        else:
                            st.error("이미지 생성에 실패했습니다")
        
        st.divider()
        
        if st.session_state.generated_images:
            st.markdown(f"### 생성된 이미지 ({len(st.session_state.generated_images)}장)")
            
            cols = st.columns(2)
            for idx, img_data in enumerate(st.session_state.generated_images):
                with cols[idx % 2]:
                    st.image(img_data["image"], use_column_width=True)
                    st.caption(f"이미지 {idx+1}")
                    
                    buffer = BytesIO(img_data["bytes"])
                    st.download_button(
                        f"💾 이미지 {idx+1} 다운로드",
                        buffer,
                        file_name=f"policy_image_{idx+1}.png",
                        mime="image/png",
                        key=f"download_img_{idx}"
                    )
        else:
            st.info("이미지를 생성하려면 위의 버튼을 클릭하세요")
    
    else:
        st.info("먼저 AI 분석을 생성해주세요")

with tab4:
    st.markdown("### 4️⃣ 영상 프롬프트 생성 (10초 3종 스타일)")
    
    if st.session_state.current_analysis and "content_briefs" in st.session_state.current_analysis:
        briefs = st.session_state.current_analysis["content_briefs"]
        
        if "video_brief" in briefs:
            video_brief = briefs["video_brief"]
            
            st.info("🎬 **10초 영상 3가지 스타일**이 자동 생성됩니다: 다큐멘터리, 시네마틱, 모던 다이내믹")
            
            if st.button("🎬 10초 영상 3종 프롬프트 생성", use_container_width=True, type="primary"):
                with st.spinner("3가지 스타일의 영상 프롬프트 생성 중..."):
                    prompts_3styles = generate_video_prompts_3styles(video_brief)
                    
                    if "video_prompts_3styles" not in st.session_state:
                        st.session_state.video_prompts_3styles = []
                    
                    st.session_state.video_prompts_3styles.append(prompts_3styles)
                    st.success("✅ 10초 영상 3종 프롬프트가 생성되었습니다!")
                    st.balloons()
            
            st.divider()
            
            # 3종 스타일 프롬프트 표시
            if "video_prompts_3styles" in st.session_state and st.session_state.video_prompts_3styles:
                st.markdown("### 📹 생성된 영상 프롬프트")
                
                for set_idx, prompt_set in enumerate(st.session_state.video_prompts_3styles):
                    st.markdown(f"#### 세트 {set_idx + 1}")
                    
                    # 스타일 1: 다큐멘터리
                    with st.expander("🎥 스타일 1: 다큐멘터리 리얼리즘", expanded=True):
                        st.text_area(
                            "프롬프트 (다큐멘터리)",
                            prompt_set["documentary"],
                            height=400,
                            key=f"video_doc_{set_idx}"
                        )
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.download_button(
                                "💾 다운로드",
                                prompt_set["documentary"],
                                file_name=f"video_documentary_{set_idx+1}.txt",
                                mime="text/plain",
                                key=f"download_doc_{set_idx}",
                                use_container_width=True
                            )
                        with col2:
                            st.link_button("🚀 Runway", VIDEO_PLATFORMS["Runway"], use_container_width=True)
                        with col3:
                            st.link_button("🎥 Pika", VIDEO_PLATFORMS["Pika"], use_container_width=True)
                    
                    # 스타일 2: 시네마틱
                    with st.expander("🎬 스타일 2: 시네마틱 드라마", expanded=True):
                        st.text_area(
                            "프롬프트 (시네마틱)",
                            prompt_set["cinematic"],
                            height=400,
                            key=f"video_cine_{set_idx}"
                        )
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.download_button(
                                "💾 다운로드",
                                prompt_set["cinematic"],
                                file_name=f"video_cinematic_{set_idx+1}.txt",
                                mime="text/plain",
                                key=f"download_cine_{set_idx}",
                                use_container_width=True
                            )
                        with col2:
                            st.link_button("🚀 Runway", VIDEO_PLATFORMS["Runway"], use_container_width=True)
                        with col3:
                            st.link_button("🎥 Pika", VIDEO_PLATFORMS["Pika"], use_container_width=True)
                    
                    # 스타일 3: 모던 다이내믹
                    with st.expander("⚡ 스타일 3: 모던 다이내믹", expanded=True):
                        st.text_area(
                            "프롬프트 (모던)",
                            prompt_set["modern_dynamic"],
                            height=400,
                            key=f"video_modern_{set_idx}"
                        )
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.download_button(
                                "💾 다운로드",
                                prompt_set["modern_dynamic"],
                                file_name=f"video_modern_{set_idx+1}.txt",
                                mime="text/plain",
                                key=f"download_modern_{set_idx}",
                                use_container_width=True
                            )
                        with col2:
                            st.link_button("🚀 Runway", VIDEO_PLATFORMS["Runway"], use_container_width=True)
                        with col3:
                            st.link_button("🎥 Pika", VIDEO_PLATFORMS["Pika"], use_container_width=True)
                    
                    st.divider()
            else:
                st.info("위의 '10초 영상 3종 프롬프트 생성' 버튼을 클릭하세요")
        
        else:
            st.info("영상 브리프가 생성되지 않았습니다")
    
    else:
        st.info("먼저 AI 분석을 생성해주세요")

with tab5:
    st.markdown("### 5️⃣ 결과 및 내보내기")
    
    if st.session_state.current_policy_id and st.session_state.current_analysis:
        policy = get_policy(st.session_state.current_policy_id)
        
        st.markdown("#### 정책 정보")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("정책 ID", policy['id'])
        with col2:
            st.metric("카테고리", policy['category'])
        with col3:
            st.metric("대상", policy['target_audience'])
        with col4:
            st.metric("상태", policy['status'])
        
        st.markdown(f"**제목**: {policy['title']}")
        st.markdown(f"**설명**: {policy['description'][:100]}...")
        
        st.divider()
        
        st.markdown("#### 생성된 콘텐츠")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("이미지", f"{len(st.session_state.generated_images)}장")
        with col2:
            video_count = len(st.session_state.video_prompts_3styles)
            st.metric("영상 프롬프트", f"{video_count}세트")
        with col3:
            st.metric("AI 분석", "완료" if st.session_state.current_analysis else "없음")
        
        st.divider()
        
        st.markdown("#### 📥 다운로드")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📄 PDF 보고서", use_container_width=True):
                with st.spinner("PDF를 생성하고 있습니다..."):
                    pdf_bytes = create_pdf_report(policy, st.session_state.current_analysis)
                    st.download_button(
                        "💾 PDF 다운로드",
                        pdf_bytes,
                        file_name=f"policy_report_{policy['id']}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
        
        with col2:
            if st.button("📦 전체 ZIP", use_container_width=True):
                with st.spinner("ZIP 파일을 생성하고 있습니다..."):
                    image_bytes = [img['bytes'] for img in st.session_state.generated_images]
                    
                    zip_bytes = create_zip_export(
                        policy,
                        st.session_state.current_analysis,
                        images=image_bytes
                    )
                    
                    st.download_button(
                        "💾 ZIP 다운로드",
                        zip_bytes,
                        file_name=f"policy_package_{policy['id']}.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
    
    else:
        st.info("정책을 생성하고 AI 분석을 완료해주세요")
