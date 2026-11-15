"""Report branding regressions with isolated output and no database access."""
from types import SimpleNamespace

import pytest

from app.utils import pdf_generator


@pytest.mark.parametrize('kind', ['sfr', 'lfr', 'vacancies', 'expirations', 'terms'])
def test_association_logo_with_old_council_asset(tmp_path, monkeypatch, kind):
    old = tmp_path / 'residentCouncilLogoSmall.jpg'
    old.write_bytes(b'old council artwork')
    source = pdf_generator.BACKEND_ROOT / 'static/images/residentAssociationLogoSmall.jpg'

    def compile_pdf(*args, **kwargs):
        tex = (tmp_path / 'report.tex').read_text()
        assert 'residentAssociationLogoSmall.jpg' in tex
        assert 'residentCouncilLogoSmall' not in tex
        assert (tmp_path / source.name).read_bytes() == source.read_bytes()
        (tmp_path / 'report.pdf').write_bytes(b'%PDF-synthetic')
        return SimpleNamespace(stdout='', stderr='', returncode=0)

    monkeypatch.setattr(pdf_generator.subprocess, 'run', compile_pdf)
    generator = pdf_generator.PDFGenerator(str(tmp_path))
    for _ in range(2):
        generator.generate_pdf(f'{kind}_template.tex', 'report',
                               {'grouped': {}, 'rows': [], 'title': 'Test', 'generated': 'Test'})
    assert old.read_bytes() == b'old council artwork'


def test_missing_association_logo(tmp_path, monkeypatch):
    monkeypatch.setattr(pdf_generator, 'BACKEND_ROOT', tmp_path)
    generator = pdf_generator.PDFGenerator(str(tmp_path))
    with pytest.raises(pdf_generator.HTTPException, match='residentAssociationLogoSmall.jpg'):
        generator.generate_pdf('sfr_template.tex', 'report', {'grouped': {}})
