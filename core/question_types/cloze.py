import re
from .base import BaseQuestion

class ClozeQuestion(BaseQuestion):
    def to_moodle_xml(self) -> str:
        # Transform [Answer] or [=Answer] into {1:SHORTANSWER:=Answer}
        # First, find all bracketed expressions that don't look like Moodle filters
        # e.g., [Respuesta]
        
        transformed_stem = self.stem_html
        
        # Regex to find [text] where text is not empty and doesn't contain another bracket.
        # We also want to support [=text].
        # Use a function to replace it.
        def replacer(match):
            inner_text = match.group(1).strip()
            # If it already starts with '=', leave it, otherwise add '='
            if inner_text.startswith('='):
                return f"{{1:SHORTANSWER:{inner_text}}}"
            else:
                return f"{{1:SHORTANSWER:={inner_text}}}"
                
        # Only replace things that are purely text. If there's complex HTML inside brackets,
        # it might be tricky, but usually it's just text.
        transformed_stem = re.sub(r'\[([^\]]+)\]', replacer, transformed_stem)
        
        # Update stem_html temporarily for header generation
        original_stem = self.stem_html
        self.stem_html = transformed_stem
        
        q_xml = self._get_common_header('cloze')
        
        if self.feedback_correct:
            q_xml += f'    <correctfeedback format="html">\n      <text><![CDATA[{self.feedback_correct}]]></text>\n    </correctfeedback>\n'
        if self.feedback_incorrect:
            q_xml += f'    <incorrectfeedback format="html">\n      <text><![CDATA[{self.feedback_incorrect}]]></text>\n    </incorrectfeedback>\n'
        
        q_xml += '    <defaultgrade>1.0000000</defaultgrade>\n'
        q_xml += '    <penalty>0.3333333</penalty>\n'
        q_xml += '    <hidden>0</hidden>\n'
        q_xml += self._get_common_footer()
        
        # Restore original
        self.stem_html = original_stem
        
        return q_xml
