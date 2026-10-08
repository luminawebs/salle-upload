from .base import BaseQuestion


class EssayQuestion(BaseQuestion):
    """Open question ("Tipo: abierta"): the student writes the answer and the
    teacher grades it by hand. Feedback in the document goes to the grader
    information (what the teacher sees while grading) and the general feedback."""

    def to_moodle_xml(self) -> str:
        q_xml = self._get_common_header('essay')
        q_xml += '    <defaultgrade>1.0000000</defaultgrade>\n'
        q_xml += '    <penalty>0.0000000</penalty>\n'
        q_xml += '    <hidden>0</hidden>\n'
        q_xml += '    <responseformat>editor</responseformat>\n'
        q_xml += '    <responserequired>1</responserequired>\n'
        q_xml += '    <responsefieldlines>10</responsefieldlines>\n'
        q_xml += '    <attachments>0</attachments>\n'
        q_xml += '    <attachmentsrequired>0</attachmentsrequired>\n'
        grader_info = "<br>".join(f for f in (self.feedback_correct, self.feedback_incorrect) if f)
        q_xml += f'    <graderinfo format="html">\n      <text><![CDATA[{grader_info}]]></text>\n    </graderinfo>\n'
        q_xml += '    <responsetemplate format="html">\n      <text></text>\n    </responsetemplate>\n'
        q_xml += self._get_common_footer()
        return q_xml
