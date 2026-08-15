import abc

class BaseQuestion(abc.ABC):
    def __init__(self, q_num: int, stem_html: str, options: list, feedback_general: str, feedback_correct: str, feedback_incorrect: str, course_id: int, document_name: str):
        self.q_num = q_num
        self.stem_html = stem_html
        self.options = options
        self.feedback_general = feedback_general
        self.feedback_correct = feedback_correct
        self.feedback_incorrect = feedback_incorrect
        self.course_id = course_id
        self.document_name = document_name

    def _get_common_header(self, q_type: str) -> str:
        q_xml = f'<!-- question: {self.q_num}  -->\n'
        q_xml += f'  <question type="{q_type}">\n'
        q_xml += f'    <name>\n      <text><![CDATA[{self.course_id}_{self.document_name}_q{self.q_num}]]></text>\n    </name>\n'
        q_xml += f'    <questiontext format="html">\n      <text><![CDATA[{self.stem_html}]]></text>\n    </questiontext>\n'
        if self.feedback_general:
            q_xml += f'    <generalfeedback format="html">\n      <text><![CDATA[{self.feedback_general}]]></text>\n    </generalfeedback>\n'
        return q_xml

    def _get_common_footer(self) -> str:
        return '  </question>\n'

    @abc.abstractmethod
    def to_moodle_xml(self) -> str:
        pass
