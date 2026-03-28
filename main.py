from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from fastapi.middleware.cors import CORSMiddleware

# ==========================================
# 1. ตั้งค่าฐานข้อมูล
# ==========================================
SQLALCHEMY_DATABASE_URL = "sqlite:///./attendance.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class StudentDB(Base):
    __tablename__ = "students"
    student_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    grade = Column(String, default="-")
    room = Column(String, default="-")

class CourseDB(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(String, unique=True, index=True)
    course_name = Column(String)

class EnrollmentDB(Base):
    __tablename__ = "enrollments"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, index=True)
    course_id = Column(String, index=True)

class AttendanceDB(Base):
    __tablename__ = "attendances"
    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(String, index=True) 
    student_id = Column(Integer, index=True)
    date = Column(String)
    status = Column(String)
    periods = Column(Integer, default=1) # 🌟 เพิ่มคอลัมน์: จำนวนคาบ

Base.metadata.create_all(bind=engine)

# ==========================================
# 2. ตั้งค่า FastAPI
# ==========================================
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
# 3. Pydantic Models
# ==========================================
class StudentCreate(BaseModel): student_id: int; name: str; grade: str = "-"; room: str = "-"
class BulkStudentCreate(BaseModel): students: List[StudentCreate]
class CourseCreate(BaseModel): course_id: str; course_name: str
class EnrollmentCreate(BaseModel): student_id: int; course_id: str
class EnrollAllPayload(BaseModel): course_id: str
class EnrollByClassPayload(BaseModel): course_id: str; grade: str; room: str
class AttendanceItem(BaseModel): student_id: int; status: str
class BulkAttendance(BaseModel): 
    course_id: str
    date: str
    periods: int = 1 # 🌟 รับจำนวนคาบจากหน้าเว็บ
    students: List[AttendanceItem]

# ==========================================
# 4. API Endpoints
# ==========================================
# 📌 API สำหรับบันทึกรายวิชาใหม่ (ส่วนที่หายไป!)
@app.post("/api/courses")
def create_course(course: CourseCreate, db: Session = Depends(get_db)):
    # เช็คก่อนว่ามีวิชานี้หรือยัง
    existing = db.query(CourseDB).filter(CourseDB.course_id == course.course_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="รหัสวิชานี้มีอยู่แล้ว")
    
    # ถ้ายังไม่มี ให้บันทึกลงฐานข้อมูล
    new_course = CourseDB(course_id=course.course_id, course_name=course.course_name)
    db.add(new_course)
    db.commit()
    return {"message": "บันทึกรายวิชาสำเร็จ"}

@app.post("/api/students/bulk")
def create_bulk_students(payload: BulkStudentCreate, db: Session = Depends(get_db)):
    processed = 0
    for stu in payload.students:
        existing = db.query(StudentDB).filter(StudentDB.student_id == stu.student_id).first()
        if existing:
            existing.name = stu.name; existing.grade = stu.grade; existing.room = stu.room
        else:
            db.add(StudentDB(student_id=stu.student_id, name=stu.name, grade=stu.grade, room=stu.room))
        processed += 1
    db.commit()
    return {"message": f"อัปโหลดและอัปเดตสำเร็จ {processed} คน"}

@app.post("/api/enrollments/all")
def enroll_all_students(payload: EnrollAllPayload, db: Session = Depends(get_db)):
    # 🌟 1. เช็คก่อนว่าวิชานี้มีการสร้างไว้ในระบบหรือยัง
    course_exists = db.query(CourseDB).filter(CourseDB.course_id == payload.course_id).first()
    if not course_exists:
        raise HTTPException(status_code=404, detail="ไม่พบรหัสวิชานี้ในระบบ กรุณาเพิ่มวิชาใหม่ที่ช่อง '1. เพิ่มวิชาเรียนใหม่' ก่อนครับ")

    # 🌟 2. ถ้าวิชามีจริง ค่อยดึงเด็กมาลงทะเบียน
    students = db.query(StudentDB).all()
    count = 0
    for stu in students:
        if not db.query(EnrollmentDB).filter(EnrollmentDB.student_id==stu.student_id, EnrollmentDB.course_id==payload.course_id).first():
            db.add(EnrollmentDB(student_id=stu.student_id, course_id=payload.course_id))
            count += 1
    db.commit()
    return {"message": f"นำนักเรียนเข้าวิชา {payload.course_id} เหมาเข่ง {count} คน สำเร็จ!"}

@app.post("/api/enrollments/by-class")
def enroll_by_class(payload: EnrollByClassPayload, db: Session = Depends(get_db)):
    # 🌟 1. เช็คก่อนว่าวิชานี้มีการสร้างไว้ในระบบหรือยัง
    course_exists = db.query(CourseDB).filter(CourseDB.course_id == payload.course_id).first()
    if not course_exists:
        raise HTTPException(status_code=404, detail="ไม่พบรหัสวิชานี้ในระบบ กรุณาเพิ่มวิชาใหม่ที่ช่อง '1. เพิ่มวิชาเรียนใหม่' ก่อนครับ")

    # 🌟 2. ถ้าวิชามีจริง ค่อยดึงเด็กตามชั้น/ห้อง มาลงทะเบียน
    query = db.query(StudentDB)
    if payload.grade and payload.grade != "-": query = query.filter(StudentDB.grade == payload.grade)
    if payload.room and payload.room != "-": query = query.filter(StudentDB.room == payload.room)
    
    students = query.all()
    if not students: raise HTTPException(status_code=404, detail="ไม่พบนักเรียนในชั้น/ห้องที่ระบุ")
    
    count = 0
    for stu in students:
        if not db.query(EnrollmentDB).filter(EnrollmentDB.student_id==stu.student_id, EnrollmentDB.course_id==payload.course_id).first():
            db.add(EnrollmentDB(student_id=stu.student_id, course_id=payload.course_id))
            count += 1
    db.commit()
    return {"message": f"นำนักเรียนเข้าวิชา {payload.course_id} จำนวน {count} คน สำเร็จ!"}

@app.get("/api/courses/{course_id}/students")
def get_students(course_id: str, db: Session = Depends(get_db)):
    enrolls = db.query(EnrollmentDB).filter(EnrollmentDB.course_id == course_id).all()
    students = db.query(StudentDB).filter(StudentDB.student_id.in_([e.student_id for e in enrolls])).all()
    return [{"student_id": s.student_id, "name": s.name} for s in students]

@app.post("/api/attendance")
def save_attendance(payload: BulkAttendance, db: Session = Depends(get_db)):
    count = 0
    for item in payload.students:
        existing = db.query(AttendanceDB).filter(
            AttendanceDB.student_id == item.student_id, AttendanceDB.subject_id == payload.course_id, AttendanceDB.date == payload.date
        ).first()
        if existing:
            existing.status = item.status
            existing.periods = payload.periods # 🌟 อัปเดตคาบ
        else:
            db.add(AttendanceDB(student_id=item.student_id, subject_id=payload.course_id, date=payload.date, status=item.status, periods=payload.periods))
        count += 1
    db.commit()
    return {"message": f"บันทึกข้อมูลสำเร็จ {count} รายการ"}

@app.get("/api/reports/{course_id}")
def get_attendance_report(course_id: str, db: Session = Depends(get_db)):
    # 🌟 นับจำนวนคาบทั้งหมดของวิชานี้ (เอาคาบของแต่ละวันมาบวกกัน)
    dates_periods = db.query(AttendanceDB.date, AttendanceDB.periods).filter(AttendanceDB.subject_id == course_id).distinct().all()
    total_periods = sum([dp.periods for dp in dates_periods])
    
    enrolls = db.query(EnrollmentDB).filter(EnrollmentDB.course_id == course_id).all()
    if not enrolls: return []
    students = db.query(StudentDB).filter(StudentDB.student_id.in_([e.student_id for e in enrolls])).all()
    
    report = []
    for s in students:
        student_records = db.query(AttendanceDB).filter(AttendanceDB.subject_id == course_id, AttendanceDB.student_id == s.student_id).all()
        # 🌟 นับคาบที่มาเรียน (มา หรือ สาย ถือว่าได้คาบ)
        attended_periods = sum([r.periods for r in student_records if r.status in ['present', 'late']])
        percent = (attended_periods / total_periods * 100) if total_periods > 0 else 0
        
        report.append({
            "student_id": s.student_id, "name": s.name, "total_days": total_periods,
            "attended_days": attended_periods, "percent": round(percent, 2), "is_danger": percent < 80
        })
    report.sort(key=lambda x: x['student_id'])
    return report