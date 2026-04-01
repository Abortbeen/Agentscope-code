# -*- coding: utf-8 -*-
"""NotebookTool - Edit Jupyter notebooks programmatically.

Implements R10 from the plan.
"""
import os

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse


async def notebook_edit(
    path: str,
    cell_number: int,
    new_source: str = "",
    cell_type: str | None = None,
    edit_mode: str = "replace",
) -> ToolResponse:
    """Edit a Jupyter notebook cell.

    Args:
        path: Absolute path to the .ipynb file.
        cell_number: 1-based cell index to operate on.
        new_source: New source content for the cell (used by replace, insert_before, insert_after).
        cell_type: Cell type ('code' or 'markdown'). Defaults to 'code' for new cells.
        edit_mode: One of 'replace', 'insert_before', 'insert_after', 'delete'.

    Returns:
        ToolResponse with the result of the edit operation.
    """
    try:
        import nbformat
    except ImportError:
        return ToolResponse(
            content=[TextBlock(text="Error: nbformat not installed. Run: pip install nbformat")],
        )

    if edit_mode not in ("replace", "insert_before", "insert_after", "delete"):
        return ToolResponse(
            content=[TextBlock(
                text=f"Error: Invalid edit_mode '{edit_mode}'. "
                "Must be one of: replace, insert_before, insert_after, delete",
            )],
        )

    if not os.path.isfile(path):
        return ToolResponse(
            content=[TextBlock(text=f"Error: File not found: {path}")],
        )

    try:
        with open(path, "r", encoding="utf-8") as f:
            nb = nbformat.read(f, as_version=4)
    except Exception as e:
        return ToolResponse(
            content=[TextBlock(text=f"Error reading notebook: {e}")],
        )

    num_cells = len(nb.cells)
    cell_index = cell_number - 1  # Convert to 0-based

    # Validate cell_number range
    if edit_mode in ("replace", "delete"):
        if cell_index < 0 or cell_index >= num_cells:
            return ToolResponse(
                content=[TextBlock(
                    text=f"Error: cell_number {cell_number} out of range. "
                    f"Notebook has {num_cells} cell(s).",
                )],
            )
    elif edit_mode in ("insert_before", "insert_after"):
        # For inserts, allow cell_number up to num_cells + 1
        if cell_index < 0 or cell_index > num_cells:
            return ToolResponse(
                content=[TextBlock(
                    text=f"Error: cell_number {cell_number} out of range for insert. "
                    f"Notebook has {num_cells} cell(s).",
                )],
            )

    resolved_type = cell_type or "code"

    try:
        if edit_mode == "replace":
            nb.cells[cell_index].source = new_source
            if cell_type:
                nb.cells[cell_index].cell_type = cell_type
            action = f"Replaced cell {cell_number}"

        elif edit_mode == "delete":
            deleted_type = nb.cells[cell_index].cell_type
            del nb.cells[cell_index]
            action = f"Deleted {deleted_type} cell {cell_number}"

        elif edit_mode == "insert_before":
            new_cell = nbformat.v4.new_code_cell(source=new_source) if resolved_type == "code" \
                else nbformat.v4.new_markdown_cell(source=new_source)
            nb.cells.insert(cell_index, new_cell)
            action = f"Inserted {resolved_type} cell before cell {cell_number}"

        elif edit_mode == "insert_after":
            new_cell = nbformat.v4.new_code_cell(source=new_source) if resolved_type == "code" \
                else nbformat.v4.new_markdown_cell(source=new_source)
            nb.cells.insert(cell_index + 1, new_cell)
            action = f"Inserted {resolved_type} cell after cell {cell_number}"

        with open(path, "w", encoding="utf-8") as f:
            nbformat.write(nb, f)

        return ToolResponse(
            content=[TextBlock(
                text=f"{action} in {path}. Notebook now has {len(nb.cells)} cell(s).",
            )],
        )

    except Exception as e:
        return ToolResponse(
            content=[TextBlock(text=f"Error editing notebook: {e}")],
        )
