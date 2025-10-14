from sqlalchemy import Column, String, Text, ForeignKey,UniqueConstraint, Integer
from sqlalchemy.orm import relationship
from db import Base

class Problems(Base):
    __tablename__ = "problems"
    
    id = Column(Integer, primary_key=True, index=True)
    problem_id = Column(Integer, nullable=False)
    question = Column(Text, nullable=False)
    difficulty = Column(String)
    url = Column(Text)
    starter_code = Column(Text)
    solutions = Column(Text)
    dataset_type = Column(String, nullable=False)
    
    test_cases = relationship(
        "TestCases",
        back_populates = "problem",
        cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        UniqueConstraint('problem_id', 'dataset_type', name='uq_challenge_problem_dataset'),
    )
    
class TestCases(Base):
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True)
    problem_id = Column(Integer, ForeignKey("problems.id"), nullable=False, index=True)
    input_data = Column(Text, nullable=False)
    output_data = Column(Text, nullable=False)
    
    problem = relationship("Problems", back_populates="test_cases")
    