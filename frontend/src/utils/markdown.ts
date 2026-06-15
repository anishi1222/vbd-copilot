export function stripHtmlComments(markdown: string): string {
  let result = "";
  let index = 0;

  while (index < markdown.length) {
    const start = markdown.indexOf("<!--", index);
    if (start === -1) {
      result += markdown.slice(index);
      break;
    }

    result += markdown.slice(index, start);
    const end = markdown.indexOf("-->", start + 4);
    if (end === -1) {
      break;
    }

    index = end + 3;
  }

  return result;
}
