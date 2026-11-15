# Document logos

`residentAssociationLogoSmall.jpg` is the Residents Association logo used by all
five roster-report templates and welcome letters. Letters remain signed by the
Council president: residents automatically belong to the Association.

The JPEG was extracted without recompression from the approved, preserved
`residentAssociationLogoSmall.pdf` using `pdfimages -j`. It is 980 × 303 RGB
pixels. The original source PDF is tracked alongside the runtime JPEG.

Reports stage the Association JPEG in their output directory; letters stage it
in their temporary compilation directory. Templates name the Association asset,
so previously staged Council files cannot select the old artwork. Reports use
the source PDF's 235-point width; letters retain their explicit 2.25-inch width.

Asset changes require a backend image rebuild and deployment. Existing generated
or published PDFs are not automatically rewritten. Validate with synthetic data
and IONOS publishing disabled unless publication is explicitly authorized.
