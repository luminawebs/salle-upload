from bs4 import BeautifulSoup
import re
from .base import BaseQuestion

class MultichoiceQuestion(BaseQuestion):
    def __init__(self, *args, is_true_false=False, correct_is_true=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_true_false = is_true_false
        self.correct_is_true = correct_is_true

    def to_moodle_xml(self) -> str:
        q_type = 'truefalse' if self.is_true_false else ('multichoice' if self.options else 'description')
        q_xml = self._get_common_header(q_type)
        
        if q_type != 'description':
            if self.feedback_correct:
                q_xml += f'    <correctfeedback format="html">\n      <text><![CDATA[{self.feedback_correct}]]></text>\n    </correctfeedback>\n'
            if self.feedback_incorrect:
                q_xml += f'    <incorrectfeedback format="html">\n      <text><![CDATA[{self.feedback_incorrect}]]></text>\n    </incorrectfeedback>\n'
            q_xml += '    <defaultgrade>1.0000000</defaultgrade>\n'
            q_xml += '    <penalty>0.3333333</penalty>\n'
            q_xml += '    <hidden>0</hidden>\n'
            
        if q_type == 'truefalse':
            q_xml += f'    <answer fraction="{"100" if self.correct_is_true else "0"}" format="moodle_auto_format">\n      <text>true</text>\n    </answer>\n'
            q_xml += f'    <answer fraction="{"0" if self.correct_is_true else "100"}" format="moodle_auto_format">\n      <text>false</text>\n    </answer>\n'
        elif q_type == 'multichoice':
            q_xml += '    <single>true</single>\n'
            q_xml += '    <shuffleanswers>true</shuffleanswers>\n'
            q_xml += '    <answernumbering>abc</answernumbering>\n'
            for opt_html, is_correct in self.options:
                fraction = "100" if is_correct else "0"
                opt_soup = BeautifulSoup(opt_html, 'html.parser')
                first_text = opt_soup.find(string=True)
                if first_text:
                    new_text = re.sub(r'^\s*=?\s*[a-zA-Z][\.\)]\s*', '', first_text)
                    if new_text != first_text:
                        first_text.replace_with(new_text)
                        opt_html = str(opt_soup)
                q_xml += f'    <answer fraction="{fraction}" format="html">\n      <text><![CDATA[{opt_html}]]></text>\n    </answer>\n'
                
        q_xml += self._get_common_footer()
        return q_xml
