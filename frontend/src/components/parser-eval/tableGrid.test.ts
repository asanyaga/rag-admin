import { describe, it, expect } from 'vitest'
import { htmlToModel, modelToHtml, materialize, emptyModel } from './tableGrid'
import {
  setText, toggleHeader, addRow, removeRow, addColumn, removeColumn, mergeCells, splitCell,
  type TableModel,
} from './tableGrid'

const anchorAt = (m: TableModel, r: number, c: number) =>
  m.cells.find((cell) => cell.row === r && cell.col === c)!

describe('tableGrid conversion', () => {
  it('round-trips a flat table', () => {
    const html = '<table><tr><th>H1</th><th>H2</th></tr><tr><td>a</td><td>b</td></tr></table>'
    expect(modelToHtml(htmlToModel(html))).toBe(html)
  })

  it('round-trips colspan and rowspan', () => {
    const html = '<table><tr><th colspan="2">Top</th></tr>'
      + '<tr><td rowspan="2">L</td><td>b</td></tr><tr><td>c</td></tr></table>'
    expect(modelToHtml(htmlToModel(html))).toBe(html)
  })

  it('escapes text like the backend serializer', () => {
    const m = emptyModel(1, 1)
    m.cells[0].text = 'a < b & "c"'
    expect(modelToHtml(m)).toBe('<table><tr><td>a &lt; b &amp; &quot;c&quot;</td></tr></table>')
  })

  it('materialize marks covered slots for a colspan', () => {
    const grid = materialize(htmlToModel('<table><tr><td colspan="2">x</td></tr></table>'))
    expect(grid[0][0].kind).toBe('anchor')
    expect(grid[0][1].kind).toBe('covered')
  })

  it('fills ragged rows with empty cells', () => {
    const m = htmlToModel('<table><tr><td>a</td><td>b</td></tr><tr><td>c</td></tr></table>')
    expect(m.rows).toBe(2)
    expect(m.cols).toBe(2)
    expect(m.cells).toHaveLength(4)
  })
})

describe('tableGrid operations', () => {
  it('setText and toggleHeader mutate the anchor', () => {
    let m = emptyModel(1, 1)
    m = setText(m, 0, 0, 'hi')
    m = toggleHeader(m, 0, 0)
    expect(anchorAt(m, 0, 0).text).toBe('hi')
    expect(anchorAt(m, 0, 0).isHeader).toBe(true)
  })

  it('addRow grows dimensions and shifts lower cells', () => {
    const m = addRow(emptyModel(2, 2), 1)
    expect(m.rows).toBe(3)
    expect(m.cells.filter((c) => c.row === 1)).toHaveLength(2)
  })

  it('addColumn extends a crossing colspan', () => {
    let m = emptyModel(1, 2)
    m = mergeCells(m, 0, 0, 0, 1)
    m = addColumn(m, 1)
    expect(anchorAt(m, 0, 0).colspan).toBe(3)
  })

  it('removeRow deletes a plain row', () => {
    const m = removeRow(emptyModel(2, 2), 0)
    expect(m.rows).toBe(1)
  })

  it('removeRow rejects slicing a rowspan', () => {
    let m = emptyModel(2, 1)
    m = mergeCells(m, 0, 0, 1, 0)
    expect(() => removeRow(m, 0)).toThrow()
  })

  it('mergeCells joins a rectangle and materialize covers it', () => {
    let m = emptyModel(2, 2)
    m = setText(m, 0, 0, 'a')
    m = setText(m, 0, 1, 'b')
    m = mergeCells(m, 0, 0, 0, 1)
    expect(anchorAt(m, 0, 0).colspan).toBe(2)
    expect(anchorAt(m, 0, 0).text).toBe('a b')
    expect(materialize(m)[0][1].kind).toBe('covered')
  })

  it('mergeCells rejects a selection overlapping an existing span', () => {
    let m = emptyModel(2, 2)
    m = mergeCells(m, 0, 0, 1, 0)
    expect(() => mergeCells(m, 0, 0, 0, 1)).toThrow()
  })

  it('splitCell restores 1x1 anchors', () => {
    let m = emptyModel(2, 2)
    m = mergeCells(m, 0, 0, 1, 1)
    m = splitCell(m, 0, 0)
    expect(anchorAt(m, 0, 0).rowspan).toBe(1)
    expect(anchorAt(m, 0, 0).colspan).toBe(1)
    expect(m.cells).toHaveLength(4)
  })
})
