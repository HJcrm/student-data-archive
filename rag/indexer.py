"""벡터 임베딩 생성 및 ChromaDB 인덱싱"""

import json
from pathlib import Path
from typing import Optional
import os

from openai import OpenAI

# ChromaDB는 선택적 import
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    print("[경고] chromadb가 설치되지 않았습니다. pip install chromadb")


class RAGIndexer:
    """RAG 벡터 인덱서"""

    def __init__(self, api_key: Optional[str] = None, db_path: str = "data/vectordb"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY가 필요합니다")

        self.client = OpenAI(api_key=self.api_key)
        self.embedding_model = "text-embedding-ada-002"
        self.db_path = Path(db_path)

        # ChromaDB 클라이언트
        if CHROMADB_AVAILABLE:
            self.db_path.mkdir(parents=True, exist_ok=True)
            self.chroma_client = chromadb.PersistentClient(path=str(self.db_path))
        else:
            self.chroma_client = None

    def create_embedding(self, text: str) -> list[float]:
        """단일 텍스트 임베딩 생성"""
        response = self.client.embeddings.create(
            model=self.embedding_model,
            input=text
        )
        return response.data[0].embedding

    def create_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """배치 임베딩 생성"""
        # OpenAI는 한 번에 최대 2048개 텍스트 처리 가능
        embeddings = []
        batch_size = 100

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=batch
            )
            embeddings.extend([d.embedding for d in response.data])
            print(f"    임베딩 생성: {min(i + batch_size, len(texts))}/{len(texts)}")

        return embeddings

    def index_from_metadata(self, metadata_dir: Path):
        """메타데이터 디렉토리에서 인덱싱"""
        metadata_dir = Path(metadata_dir)

        # 데이터 로드
        with open(metadata_dir / "students.json", "r", encoding="utf-8") as f:
            students = json.load(f)
        with open(metadata_dir / "research.json", "r", encoding="utf-8") as f:
            research_list = json.load(f)
        with open(metadata_dir / "saeteuk.json", "r", encoding="utf-8") as f:
            saeteuk_list = json.load(f)

        print(f"\n[인덱싱 시작]")
        print(f"  학생: {len(students)}명")
        print(f"  탐구활동: {len(research_list)}개")
        print(f"  세특: {len(saeteuk_list)}개")

        # 학생 ID → 프로필 매핑
        student_map = {s["id"]: s for s in students}

        # 탐구활동 인덱싱
        print(f"\n[탐구활동 임베딩 생성]")
        research_texts = []
        research_ids = []
        research_metadata = []

        for r in research_list:
            # RAG 텍스트 생성
            text = self._create_research_text(r, student_map.get(r["student_id"], {}))
            research_texts.append(text)
            research_ids.append(r["id"])
            research_metadata.append(self._create_research_metadata(r, student_map.get(r["student_id"], {})))

        research_embeddings = self.create_embeddings_batch(research_texts)

        # 세특 인덱싱
        print(f"\n[세특 임베딩 생성]")
        saeteuk_texts = []
        saeteuk_ids = []
        saeteuk_metadata = []

        for s in saeteuk_list:
            text = self._create_saeteuk_text(s, student_map.get(s["student_id"], {}))
            saeteuk_texts.append(text)
            saeteuk_ids.append(s["id"])
            saeteuk_metadata.append(self._create_saeteuk_metadata(s, student_map.get(s["student_id"], {})))

        saeteuk_embeddings = self.create_embeddings_batch(saeteuk_texts)

        # ChromaDB에 저장
        if self.chroma_client:
            self._save_to_chromadb(
                "research", research_ids, research_texts, research_embeddings, research_metadata
            )
            self._save_to_chromadb(
                "saeteuk", saeteuk_ids, saeteuk_texts, saeteuk_embeddings, saeteuk_metadata
            )

        # JSON으로도 저장 (백업)
        self._save_embeddings_json(
            metadata_dir,
            research_list, research_embeddings,
            saeteuk_list, saeteuk_embeddings
        )

        print(f"\n[인덱싱 완료]")
        print(f"  ChromaDB: {self.db_path}")
        print(f"  탐구활동 벡터: {len(research_embeddings)}개")
        print(f"  세특 벡터: {len(saeteuk_embeddings)}개")

    def _create_research_text(self, research: dict, student: dict) -> str:
        """탐구활동 검색용 텍스트 생성"""
        parts = []

        # 학생 컨텍스트
        if student.get("major_field"):
            parts.append(f"계열: {student['major_field']}")
        if student.get("final_university"):
            parts.append(f"대학: {student['final_university']}")

        # 탐구 정보
        if research.get("term"):
            parts.append(f"시기: {research['term']}")
        if research.get("subject"):
            parts.append(f"과목: {research['subject']}")
        if research.get("title"):
            parts.append(f"주제: {research['title']}")

        return " | ".join(parts)

    def _create_saeteuk_text(self, saeteuk: dict, student: dict) -> str:
        """세특 검색용 텍스트 생성"""
        parts = []

        # 학생 컨텍스트
        if student.get("major_field"):
            parts.append(f"계열: {student['major_field']}")

        # 세특 정보
        if saeteuk.get("subject"):
            parts.append(f"과목: {saeteuk['subject']}")
        if saeteuk.get("content"):
            # 내용 앞부분만 사용 (임베딩 효율)
            content = saeteuk["content"][:800]
            parts.append(f"내용: {content}")

        return " | ".join(parts)

    def _create_research_metadata(self, research: dict, student: dict) -> dict:
        """탐구활동 메타데이터 (필터링용)"""
        return {
            "type": "research",
            "student_id": research.get("student_id", ""),
            "term": research.get("term", ""),
            "grade": research.get("grade", 0),
            "subject": research.get("subject", ""),
            "major_field": student.get("major_field", ""),
            "nesin_range": student.get("nesin_range", ""),
            "university": student.get("final_university", ""),
            "school_type": student.get("school_type", ""),
        }

    def _create_saeteuk_metadata(self, saeteuk: dict, student: dict) -> dict:
        """세특 메타데이터 (필터링용)"""
        return {
            "type": "saeteuk",
            "student_id": saeteuk.get("student_id", ""),
            "subject": saeteuk.get("subject", ""),
            "major_field": student.get("major_field", ""),
            "nesin_range": student.get("nesin_range", ""),
            "university": student.get("final_university", ""),
            "school_type": student.get("school_type", ""),
        }

    def _save_to_chromadb(
        self,
        collection_name: str,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict]
    ):
        """ChromaDB에 저장"""
        # 기존 컬렉션 삭제 후 재생성
        try:
            self.chroma_client.delete_collection(collection_name)
        except:
            pass

        collection = self.chroma_client.create_collection(
            name=collection_name,
            metadata={"description": f"RAG {collection_name} collection"}
        )

        collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )

        print(f"    ChromaDB '{collection_name}' 컬렉션: {len(ids)}개 문서")

    def _save_embeddings_json(
        self,
        output_dir: Path,
        research_list: list,
        research_embeddings: list,
        saeteuk_list: list,
        saeteuk_embeddings: list
    ):
        """임베딩을 JSON으로 저장 (백업)"""
        # 탐구활동 + 임베딩
        for i, r in enumerate(research_list):
            r["embedding"] = research_embeddings[i]

        with open(output_dir / "research_with_embeddings.json", "w", encoding="utf-8") as f:
            json.dump(research_list, f, ensure_ascii=False)

        # 세특 + 임베딩
        for i, s in enumerate(saeteuk_list):
            s["embedding"] = saeteuk_embeddings[i]

        with open(output_dir / "saeteuk_with_embeddings.json", "w", encoding="utf-8") as f:
            json.dump(saeteuk_list, f, ensure_ascii=False)

        print(f"    JSON 백업 저장 완료")
