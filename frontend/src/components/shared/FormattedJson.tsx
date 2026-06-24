interface FormattedJsonProps {
  value: unknown
  maxHeight?: string
}

function highlight(json: string): React.ReactNode[] {
  // Groups: (1) quoted string + optional colon (key vs. value), (2) bool/null, (3) number
  const regex =
    /("(?:[^\\"]|\\.)*")(\s*:)?|(\btrue\b|\bfalse\b|\bnull\b)|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g
  const nodes: React.ReactNode[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = regex.exec(json)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(json.slice(lastIndex, match.index))
    }
    if (match[1] !== undefined) {
      const isKey = match[2] !== undefined
      nodes.push(
        <span
          key={match.index}
          className={
            isKey
              ? 'text-blue-700 dark:text-blue-400'
              : 'text-green-700 dark:text-green-400'
          }
        >
          {match[1]}
        </span>
      )
      if (match[2]) nodes.push(match[2])
    } else if (match[3] !== undefined) {
      nodes.push(
        <span key={match.index} className="text-amber-600 dark:text-amber-400">
          {match[3]}
        </span>
      )
    } else if (match[4] !== undefined) {
      nodes.push(
        <span key={match.index} className="text-amber-600 dark:text-amber-400">
          {match[4]}
        </span>
      )
    }
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < json.length) nodes.push(json.slice(lastIndex))
  return nodes
}

export function FormattedJson({ value, maxHeight = '24rem' }: FormattedJsonProps) {
  if (value === null || value === undefined) {
    return (
      <pre
        className="text-xs font-mono bg-muted p-3 rounded-md border overflow-auto text-muted-foreground"
        style={{ maxHeight }}
      >
        {String(value)}
      </pre>
    )
  }
  const json = JSON.stringify(value, null, 2)
  return (
    <pre
      className="text-xs font-mono bg-muted p-3 rounded-md border overflow-auto"
      style={{ maxHeight }}
    >
      {highlight(json)}
    </pre>
  )
}
