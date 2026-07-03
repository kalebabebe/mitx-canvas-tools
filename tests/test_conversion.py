"""
End-to-end tests for the Canvas → OLX conversion pipeline.
"""

from pathlib import Path


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestParser:
    def test_parse_course_settings_and_modules(self, fixture_imscc):
        from src.parsers.canvas_parser import CanvasParser

        with CanvasParser() as parser:
            data = parser.parse(str(fixture_imscc))

            assert data["title"] == "Test Course"
            assert data["course_code"] == "TC101"
            assert len(data["modules"]) == 1

            module = data["modules"][0]
            assert module["title"] == "Week 1"
            assert len(module["items"]) == 3
            types = [i["content_type"] for i in module["items"]]
            assert types == ["WikiPage", "Quizzes::Quiz", "ExternalUrl"]

    def test_wiki_page_content(self, fixture_imscc):
        from src.parsers.canvas_parser import CanvasParser

        with CanvasParser() as parser:
            parser.parse(str(fixture_imscc))
            content = parser.get_wiki_page_content("g_wiki_intro")
            assert content is not None
            assert "Welcome" in content

    def test_front_page_detected(self, fixture_imscc):
        from src.parsers.canvas_parser import CanvasParser

        with CanvasParser() as parser:
            parser.parse(str(fixture_imscc))
            front = parser.get_front_page()
            assert front is not None
            identifier, html = front
            assert identifier == "g_wiki_home"
            assert "home page" in html


class TestQTIParser:
    def test_multiple_choice_parsed(self, fixture_imscc, tmp_path):
        import zipfile
        from src.parsers.qti_parser import QTIParser

        with zipfile.ZipFile(fixture_imscc) as z:
            z.extractall(tmp_path)

        quiz = QTIParser().parse_quiz(tmp_path / "gquiz1" / "assessment_qti.xml")
        assert quiz["title"] == "Quiz 1"
        assert len(quiz["questions"]) == 1

        q = quiz["questions"][0]
        assert q["type"] == "multiple_choice"
        assert q["points"] == 2.0
        assert [c["text"] for c in q["choices"]] == ["3", "4", "5"]
        assert q["correct_answers"] == ["c2"]


class TestFullConversion:
    def test_report_statistics(self, converted):
        report, _ = converted
        assert report["course_title"] == "Test Course"
        stats = report["statistics"]
        # Week 1 + Import Notes (from skipped ExternalUrl)
        assert stats["chapters"] == 2
        assert stats["components"] >= 2  # wiki html + quiz problem
        assert stats["assets"] == 1

    def test_skipped_and_timed_items_reported(self, converted):
        report, _ = converted

        skipped = report["skipped_items"]
        assert any(i["title"] == "MIT Homepage" for i in skipped)

        timed = report["timed_quizzes"]
        assert len(timed) == 1
        assert timed[0]["time_limit"] == 30

    def test_olx_structure(self, converted):
        _, out = converted
        assert (out / "course.xml").exists()
        assert (out / "chapter").is_dir()
        assert (out / "problem").is_dir()
        assert (out / "html").is_dir()
        # asset copied to static
        assert (out / "static" / "images" / "logo.png").exists()

    def test_problem_content(self, converted):
        _, out = converted
        problems = list((out / "problem").glob("*.xml"))
        assert len(problems) == 1
        xml = read(problems[0])
        assert "<multiplechoiceresponse" in xml
        assert 'correct="true"' in xml
        assert "4" in xml

    def test_wiki_html_asset_urls_rewritten(self, converted):
        _, out = converted
        html_files = [read(p) for p in (out / "html").glob("*.html")]
        combined = "\n".join(html_files)
        assert "$IMS-CC-FILEBASE$" not in combined
        assert "/static/" in combined

    def test_front_page_becomes_updates(self, converted):
        _, out = converted
        updates = out / "info" / "updates.html"
        assert updates.exists()
        assert "home page" in read(updates)
