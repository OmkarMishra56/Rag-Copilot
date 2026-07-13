from app.core.chunking import build_parent_child_chunks, count_tokens, recursive_chunk, semantic_chunk


def test_recursive_chunk_respects_size():
    text = "Sentence one. " * 500
    chunks = recursive_chunk(text, chunk_size=50, overlap=0)
    assert all(count_tokens(c) <= 60 for c in chunks)  # small slack for overlap/boundary
    assert len(chunks) > 1


def test_recursive_chunk_short_text_single_chunk():
    text = "A short document."
    chunks = recursive_chunk(text, chunk_size=800)
    assert chunks == [text]


def test_semantic_chunk_preserves_headings():
    text = "# Intro\nSome intro text.\n\n## Details\nMore detail text here that is fairly short."
    chunks = semantic_chunk(text, chunk_size=800)
    assert len(chunks) >= 1
    assert "Intro" in "".join(chunks)


def test_parent_child_chunks_link_correctly():
    text = "Paragraph one. " * 200 + "\n\n" + "Paragraph two. " * 200
    parents, children = build_parent_child_chunks(text, parent_size=300, child_size=60)
    assert len(parents) >= 1
    assert len(children) >= len(parents)
    parent_ids = {p.id for p in parents}
    assert all(c.parent_id in parent_ids for c in children)
