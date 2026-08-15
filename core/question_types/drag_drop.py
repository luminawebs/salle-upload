from bs4 import BeautifulSoup
import re
from .base import BaseQuestion

class DragDropQuestion(BaseQuestion):
    def to_moodle_xml(self) -> str:
        q_xml = self._get_common_header('ddwtos')
        
        q_xml += '    <shuffleanswers>1</shuffleanswers>\n'
        q_xml += '    <defaultgrade>1.0000000</defaultgrade>\n'
        q_xml += '    <penalty>0.3333333</penalty>\n'
        q_xml += '    <hidden>0</hidden>\n'
        
        if self.feedback_correct:
            q_xml += f'    <correctfeedback format="html">\n      <text><![CDATA[{self.feedback_correct}]]></text>\n    </correctfeedback>\n'
        if self.feedback_incorrect:
            q_xml += f'    <incorrectfeedback format="html">\n      <text><![CDATA[{self.feedback_incorrect}]]></text>\n    </incorrectfeedback>\n'
            
        q_xml += '    <dragboxes>\n'
        
        # Options are the draggable texts
        for idx, (opt_html, is_correct) in enumerate(self.options, 1):
            opt_soup = BeautifulSoup(opt_html, 'html.parser')
            opt_text = opt_soup.get_text(strip=True)
            
            # Clean up letters like A. B. C. if present, though typically they won't be
            new_text = re.sub(r'^\s*=?\s*[a-zA-Z][\.\)]\s*', '', opt_text)
            
            q_xml += '      <dragbox>\n'
            q_xml += f'        <text><![CDATA[{new_text}]]></text>\n'
            q_xml += '        <group>1</group>\n'
            q_xml += '      </dragbox>\n'
            
        q_xml += '    </dragboxes>\n'
        q_xml += self._get_common_footer()
        return q_xml
