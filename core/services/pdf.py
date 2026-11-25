import re
import unicodedata
from fpdf import FPDF


def _clean(text):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[*_`#>]+", "", text)  # strip markdown markers
    # break very long tokens so fpdf never runs out of horizontal space
    return " ".join(w if len(w) < 60 else " ".join(w[i:i + 50] for i in range(0, len(w), 50))
                    for w in text.split(" "))


def build_course_pdf(course):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    def write(txt, size=11, bold=False, gap=6):
        pdf.set_font("Helvetica", "B" if bold else "", size)
        for line in _clean(txt).split("\n"):
            pdf.multi_cell(0, gap, line.strip() or " ", new_x="LMARGIN", new_y="NEXT")

    write(f"COURSE: {course.name}", 18, True, 10)
    write(f"Level: {course.level} | Audience: {course.audience} | Duration: {course.duration} | Credits: {course.credit}", 10)
    pdf.ln(4)
    write("Outline", 14, True, 8)
    write(course.outline, 10)

    for m in course.modules.prefetch_related("questions"):
        pdf.add_page()
        write(m.title, 15, True, 9)
        write(m.content, 10)
        pdf.ln(4)
        write(f"Quiz - {m.title}", 13, True, 8)
        for i, q in enumerate(m.questions.all(), start=1):
            write(f"Q{i}. {q.text}", 10, True)
            for k, v in q.options:
                write(f"   {k}) {v}", 10)
            write(f"   Answer: {q.answer}", 10)
            if q.explanation:
                write(f"   Explanation: {q.explanation}", 10)
            pdf.ln(2)
    return bytes(pdf.output())
