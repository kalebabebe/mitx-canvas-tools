"""
Test fixtures: builds a minimal but realistic Canvas .imscc export in-memory.
"""

import zipfile
from pathlib import Path

import pytest

WIKI_ID = "g_wiki_intro"
FRONT_PAGE_ID = "g_wiki_home"
QUIZ_ID = "gquiz1"

COURSE_SETTINGS = """<?xml version="1.0" encoding="UTF-8"?>
<course identifier="g_course_1">
  <title>Test Course</title>
  <course_code>TC101</course_code>
  <start_at>2026-01-01T00:00:00-05:00</start_at>
</course>
"""

MODULE_META = f"""<?xml version="1.0" encoding="UTF-8"?>
<modules>
  <module identifier="g_mod_1">
    <title>Week 1</title>
    <workflow_state>active</workflow_state>
    <position>1</position>
    <items>
      <item identifier="g_item_1">
        <content_type>WikiPage</content_type>
        <title>Introduction</title>
        <identifierref>{WIKI_ID}</identifierref>
        <workflow_state>active</workflow_state>
        <position>1</position>
      </item>
      <item identifier="g_item_2">
        <content_type>Quizzes::Quiz</content_type>
        <title>Quiz 1</title>
        <identifierref>{QUIZ_ID}</identifierref>
        <workflow_state>active</workflow_state>
        <position>2</position>
      </item>
      <item identifier="g_item_3">
        <content_type>ExternalUrl</content_type>
        <title>MIT Homepage</title>
        <workflow_state>active</workflow_state>
        <position>3</position>
        <url>https://web.mit.edu</url>
      </item>
    </items>
  </module>
</modules>
"""

WIKI_PAGE = f"""<html>
<head>
<meta name="identifier" content="{WIKI_ID}"/>
<meta name="editing_roles" content="teachers"/>
<meta name="workflow_state" content="active"/>
<title>Introduction</title>
</head>
<body>
<h2>Welcome</h2>
<p>Course intro text.</p>
<p><img src="$IMS-CC-FILEBASE$/images/logo.png" alt="logo"/></p>
</body>
</html>
"""

FRONT_PAGE = f"""<html>
<head>
<meta name="identifier" content="{FRONT_PAGE_ID}"/>
<meta name="front_page" content="true"/>
<meta name="workflow_state" content="active"/>
<title>Home</title>
</head>
<body>
<p>This is the course home page.</p>
</body>
</html>
"""

ASSESSMENT_QTI = f"""<?xml version="1.0" encoding="UTF-8"?>
<questestinterop>
  <assessment ident="{QUIZ_ID}" title="Quiz 1">
    <section ident="root_section">
      <item ident="q1" title="Arithmetic">
        <itemmetadata>
          <qtimetadata>
            <qtimetadatafield>
              <fieldlabel>question_type</fieldlabel>
              <fieldentry>multiple_choice_question</fieldentry>
            </qtimetadatafield>
            <qtimetadatafield>
              <fieldlabel>points_possible</fieldlabel>
              <fieldentry>2.0</fieldentry>
            </qtimetadatafield>
          </qtimetadata>
        </itemmetadata>
        <presentation>
          <material>
            <mattext texttype="text/html">&lt;p&gt;What is 2+2?&lt;/p&gt;</mattext>
          </material>
          <response_lid ident="response1" rcardinality="Single">
            <render_choice>
              <response_label ident="c1">
                <material><mattext texttype="text/plain">3</mattext></material>
              </response_label>
              <response_label ident="c2">
                <material><mattext texttype="text/plain">4</mattext></material>
              </response_label>
              <response_label ident="c3">
                <material><mattext texttype="text/plain">5</mattext></material>
              </response_label>
            </render_choice>
          </response_lid>
        </presentation>
        <resprocessing>
          <outcomes>
            <decvar maxvalue="100" minvalue="0" varname="SCORE" vartype="Decimal"/>
          </outcomes>
          <respcondition continue="No">
            <conditionvar><varequal respident="response1">c2</varequal></conditionvar>
            <setvar action="Set" varname="SCORE">100</setvar>
          </respcondition>
        </resprocessing>
      </item>
    </section>
  </assessment>
</questestinterop>
"""

ASSESSMENT_META = f"""<?xml version="1.0" encoding="UTF-8"?>
<quiz identifier="{QUIZ_ID}">
  <title>Quiz 1</title>
  <time_limit>30</time_limit>
  <allowed_attempts>2</allowed_attempts>
  <scoring_policy>keep_highest</scoring_policy>
  <show_correct_answers>true</show_correct_answers>
  <points_possible>2.0</points_possible>
  <quiz_type>assignment</quiz_type>
</quiz>
"""

MANIFEST = """<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="g_manifest_1">
  <metadata>
    <schema>IMS Common Cartridge</schema>
    <schemaversion>1.1.0</schemaversion>
  </metadata>
  <organizations/>
  <resources/>
</manifest>
"""

# 1x1 transparent PNG
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63fcffff3f0300050201a71a4cda0000000049454e44ae426082"
)


@pytest.fixture(scope="session")
def fixture_imscc(tmp_path_factory) -> Path:
    """Create a minimal Canvas .imscc export file"""
    root = tmp_path_factory.mktemp("fixture")
    imscc = root / "test_course.imscc"

    with zipfile.ZipFile(imscc, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("imsmanifest.xml", MANIFEST)
        z.writestr("course_settings/course_settings.xml", COURSE_SETTINGS)
        z.writestr("course_settings/module_meta.xml", MODULE_META)
        z.writestr("wiki_content/introduction.html", WIKI_PAGE)
        z.writestr("wiki_content/home.html", FRONT_PAGE)
        z.writestr(f"{QUIZ_ID}/assessment_qti.xml", ASSESSMENT_QTI)
        z.writestr(f"{QUIZ_ID}/assessment_meta.xml", ASSESSMENT_META)
        z.writestr("web_resources/images/logo.png", PNG_BYTES)

    return imscc


@pytest.fixture()
def converted(fixture_imscc, tmp_path):
    """Run the full conversion pipeline once; return (report, output_dir)"""
    from src.converter import convert_canvas_to_openedx

    output_dir = tmp_path / "olx_out"
    report = convert_canvas_to_openedx(str(fixture_imscc), str(output_dir), verbose=False)
    return report, output_dir
