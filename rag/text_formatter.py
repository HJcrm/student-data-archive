"""OpenAI를 사용한 텍스트 포맷팅"""

import os
from openai import OpenAI
from typing import Optional


class TextFormatter:
    """텍스트 띄어쓰기 및 형식 정리"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY 환경변수를 설정해주세요")

        self.client = OpenAI(api_key=self.api_key)

    def format_text(self, text: str) -> str:
        """텍스트 띄어쓰기 및 형식 정리"""
        if not text or len(text) < 10:
            return text

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """당신은 한국어 텍스트 교정 전문가입니다.
주어진 텍스트의 띄어쓰기를 교정하고 가독성을 높여주세요.

규칙:
1. 띄어쓰기만 교정하고 내용은 절대 변경하지 마세요
2. 문장 부호(마침표, 쉼표) 뒤에 적절한 띄어쓰기 추가
3. 조사는 앞 단어에 붙여쓰기
4. 원본의 의미와 정보를 100% 유지
5. 줄바꿈은 그대로 유지

JSON 형식으로 응답하세요: {"formatted": "교정된 텍스트"}"""
                    },
                    {
                        "role": "user",
                        "content": f"다음 텍스트의 띄어쓰기를 교정해주세요:\n\n{text}"
                    }
                ],
                temperature=0.1,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )

            import json
            result = json.loads(response.choices[0].message.content)
            return result.get("formatted", text)

        except Exception as e:
            print(f"[포맷팅 오류] {e}")
            return text

    def format_saeteuk(self, content: str) -> str:
        """세특 내용 포맷팅"""
        return self.format_text(content)

    def format_research_title(self, title: str) -> str:
        """탐구 제목 포맷팅 (간단한 경우 직접 처리)"""
        # 짧은 제목은 API 호출 없이 기본 규칙 적용
        if len(title) < 50:
            return self._basic_spacing(title)
        return self.format_text(title)

    def _basic_spacing(self, text: str) -> str:
        """기본 띄어쓰기 규칙 적용"""
        # 마침표, 쉼표 뒤 띄어쓰기
        import re
        text = re.sub(r'\.(?=[가-힣A-Za-z])', '. ', text)
        text = re.sub(r',(?=[가-힣A-Za-z])', ', ', text)
        return text

    def format_batch(self, texts: list[str]) -> list[str]:
        """여러 텍스트 개별 포맷팅 (정확도 향상)"""
        if not texts:
            return texts

        formatted_texts = []
        for i, text in enumerate(texts):
            try:
                formatted = self.format_text(text)
                formatted_texts.append(formatted)
                print(f"    텍스트 {i+1}/{len(texts)} 포맷팅 완료")
            except Exception as e:
                print(f"    텍스트 {i+1} 포맷팅 실패: {e}")
                formatted_texts.append(text)

        return formatted_texts


# 싱글톤 인스턴스
_formatter = None

def get_formatter() -> TextFormatter:
    """포맷터 인스턴스 반환"""
    global _formatter
    if _formatter is None:
        _formatter = TextFormatter()
    return _formatter
