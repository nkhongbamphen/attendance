from fastapi import FastAPI, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import List
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from fastapi.middleware.cors import CORSMiddleware

# ==========================================
# 🌟 ตั้งค่ารหัสผ่านเข้าใช้งานเว็บ (เปลี่ยนได้ตามต้องการ)
# ==========================================
ADMIN_USER = "admin"
ADMIN_PASS = "1234"
SECRET_TOKEN = "teacher-secret-token-999" # บัตรพนักงานจำลอง

# ==========================================
# 1. ตั้งค่าฐานข้อมูล (เหมือนเดิม)
# ==========================================
SQLALCHEMY_DATABASE_URL = "postgresql://neondb_owner:npg_cxkt5LpVewy4@ep-billowing-lake-a181ay80-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
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
    periods = Column(Integer, default=1)

Base.metadata.create_all(bind=engine)

app = FastAPI()

# 🌟 2. เพิ่มโค้ดอนุญาตให้หน้าเว็บเข้ามาดึงข้อมูลได้
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # อนุญาตให้ทุกเว็บเข้ามาได้ (ตอนทำจริงค่อยระบุชื่อเว็บครับ)
    allow_credentials=True,
    allow_methods=["*"],  # อนุญาตทุก Method (GET, POST, PUT, DELETE)
    allow_headers=["*"],  # อนุญาตให้ส่ง Header (เช่น Token) มาได้
)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# ==========================================
# 🌟 2. ระบบ "ยามตรวจบัตร" (ถ้าไม่มีบัตร จะเตะออกทันที)
# ==========================================
def verify_auth(authorization: str = Header(None)):
    if authorization != f"Bearer {SECRET_TOKEN}":
        raise HTTPException(status_code=401, detail="กรุณาล็อคอินก่อนใช้งาน")

# ==========================================
# 3. Pydantic Models (เพิ่ม LoginRequest)
# ==========================================
class LoginRequest(BaseModel): username: str; password: str
class StudentCreate(BaseModel): student_id: int; name: str; grade: str = "-"; room: str = "-"
class BulkStudentCreate(BaseModel): students: List[StudentCreate]
class CourseCreate(BaseModel): course_id: str; course_name: str
class EnrollmentCreate(BaseModel): student_id: int; course_id: str
class EnrollAllPayload(BaseModel): course_id: str
class EnrollByClassPayload(BaseModel): course_id: str; grade: str; room: str
class AttendanceItem(BaseModel): student_id: int; status: str
class BulkAttendance(BaseModel): course_id: str; date: str; periods: int = 1; students: List[AttendanceItem]

# ==========================================
# 4. API Endpoints
# ==========================================

# 🌟 API สำหรับล็อคอิน (ไม่ต้องมียามเฝ้า)
@app.post("/api/login")
def login(payload: LoginRequest):
    if payload.username == ADMIN_USER and payload.password == ADMIN_PASS:
        return {"access_token": SECRET_TOKEN} # แจกบัตรพนักงาน
    raise HTTPException(status_code=401, detail="Username หรือ Password ไม่ถูกต้อง")

# 🌟 API อื่นๆ ทั้งหมด ต้องมียามตรวจบัตร (dependencies=[Depends(verify_auth)])
@app.post("/api/courses", dependencies=[Depends(verify_auth)])
def create_course(course: CourseCreate, db: Session = Depends(get_db)):
    if db.query(CourseDB).filter(CourseDB.course_id == course.course_id).first():
        raise HTTPException(status_code=400, detail="รหัสวิชานี้มีอยู่แล้ว")
    db.add(CourseDB(course_id=course.course_id, course_name=course.course_name))
    db.commit()
    return {"message": "บันทึกรายวิชาสำเร็จ"}

@app.post("/api/students/bulk", dependencies=[Depends(verify_auth)])
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

@app.post("/api/enrollments/all", dependencies=[Depends(verify_auth)])
def enroll_all_students(payload: EnrollAllPayload, db: Session = Depends(get_db)):
    if not db.query(CourseDB).filter(CourseDB.course_id == payload.course_id).first():
        raise HTTPException(status_code=404, detail="ไม่พบรหัสวิชานี้ในระบบ")
    count = sum(1 for stu in db.query(StudentDB).all() if not db.query(EnrollmentDB).filter(EnrollmentDB.student_id==stu.student_id, EnrollmentDB.course_id==payload.course_id).first() and db.add(EnrollmentDB(student_id=stu.student_id, course_id=payload.course_id)) is None)
    db.commit()
    return {"message": f"นำนักเรียนเข้าวิชา {payload.course_id} สำเร็จ!"}

@app.post("/api/enrollments/by-class", dependencies=[Depends(verify_auth)])
def enroll_by_class(payload: EnrollByClassPayload, db: Session = Depends(get_db)):
    if not db.query(CourseDB).filter(CourseDB.course_id == payload.course_id).first():
        raise HTTPException(status_code=404, detail="ไม่พบรหัสวิชานี้ในระบบ")
    query = db.query(StudentDB)
    if payload.grade and payload.grade != "-": query = query.filter(StudentDB.grade == payload.grade)
    if payload.room and payload.room != "-": query = query.filter(StudentDB.room == payload.room)
    students = query.all()
    if not students: raise HTTPException(status_code=404, detail="ไม่พบนักเรียนในชั้น/ห้อง")
    count = sum(1 for stu in students if not db.query(EnrollmentDB).filter(EnrollmentDB.student_id==stu.student_id, EnrollmentDB.course_id==payload.course_id).first() and db.add(EnrollmentDB(student_id=stu.student_id, course_id=payload.course_id)) is None)
    db.commit()
    return {"message": f"นำนักเรียนเข้าวิชา {payload.course_id} สำเร็จ!"}

@app.get("/api/courses/{course_id}/students", dependencies=[Depends(verify_auth)])
def get_students(course_id: str, db: Session = Depends(get_db)):
    enrolls = db.query(EnrollmentDB).filter(EnrollmentDB.course_id == course_id).all()
    students = db.query(StudentDB).filter(StudentDB.student_id.in_([e.student_id for e in enrolls])).all()
    return [{"student_id": s.student_id, "name": s.name} for s in students]

@app.post("/api/attendance", dependencies=[Depends(verify_auth)])
def save_attendance(payload: BulkAttendance, db: Session = Depends(get_db)):
    count = 0
    for item in payload.students:
        existing = db.query(AttendanceDB).filter(AttendanceDB.student_id == item.student_id, AttendanceDB.subject_id == payload.course_id, AttendanceDB.date == payload.date).first()
        if existing:
            existing.status = item.status; existing.periods = payload.periods 
        else:
            db.add(AttendanceDB(student_id=item.student_id, subject_id=payload.course_id, date=payload.date, status=item.status, periods=payload.periods))
        count += 1
    db.commit()
    return {"message": f"บันทึกข้อมูลสำเร็จ {count} รายการ"}

@app.get("/api/reports/{course_id}", dependencies=[Depends(verify_auth)])
def get_attendance_report(course_id: str, db: Session = Depends(get_db)):
    dates_periods = db.query(AttendanceDB.date, AttendanceDB.periods).filter(AttendanceDB.subject_id == course_id).distinct().all()
    total_periods = sum([dp.periods for dp in dates_periods])
    enrolls = db.query(EnrollmentDB).filter(EnrollmentDB.course_id == course_id).all()
    if not enrolls: return []
    students = db.query(StudentDB).filter(StudentDB.student_id.in_([e.student_id for e in enrolls])).all()
    report = []
    for s in students:
        student_records = db.query(AttendanceDB).filter(AttendanceDB.subject_id == course_id, AttendanceDB.student_id == s.student_id).all()
        attended_periods = sum([r.periods for r in student_records if r.status in ['present', 'late']])
        percent = (attended_periods / total_periods * 100) if total_periods > 0 else 0
        report.append({"student_id": s.student_id, "name": s.name, "total_days": total_periods, "attended_days": attended_periods, "percent": round(percent, 2), "is_danger": percent < 80})
    report.sort(key=lambda x: x['student_id'])
    return report