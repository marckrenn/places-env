import subprocess
import re
import shutil


def filter_markdown_sections():
    # Create a copy of the original markdown file
    shutil.copy("./_build/markdown/index.md", "./_build/markdown/index-mod.md")

    # Read and filter the markdown
    with open("./_build/markdown/index-mod.md", "r") as f:
        markdown_content = f.read()

    # Remove first two lines
    markdown_lines = markdown_content.split("\n")[2:]

    filtered_lines = []
    skip_section = False

    for i, line in enumerate(markdown_lines):
        if re.match(r"^#{2,3}\s", line):
            if (
                line.strip()
                in [
                    "### Options",
                    "### Arguments",
                    "### encrypt",
                    "### decrypt",
                    "### init",
                ]
                or line.startswith("### -")
                or (
                    line.startswith("### ")
                    and re.match(r"^[A-Z0-9_]+$", line[4:].strip())
                )
            ):
                skip_section = False
            else:
                skip_section = True
        elif re.match(r"^#{4}\s", line):
            # Find the corresponding shell command
            si = i
            command = line.replace("#", "").strip()

            while si < len(markdown_lines):
                if markdown_lines[si].strip().startswith("```shell"):
                    if command in markdown_lines[si + 1]:
                        prefix = markdown_lines[si + 1].split()[1]
                        line = line.split(" ", 1)
                        line = f"{line[0]} {prefix} {line[1]}"
                        break
                    else:
                        si += 1
                else:
                    si += 1

            skip_section = False

        if not skip_section:
            if re.match(r"^#{4}\s", line):
                line = line[2:]
            elif (
                line.startswith("### encrypt")
                or line.startswith("### decrypt")
                or line.startswith("### init")
            ):
                line = line[1:]
            filtered_lines.append(line)

    # Process shell code blocks to move [OPTIONS] to the end
    filtered_lines = process_shell_codeblocks(filtered_lines)

    # Write filtered content back to index-mod.md
    with open("./_build/markdown/index-mod.md", "w") as f:
        f.write("\n".join(filtered_lines))

    return filtered_lines


def process_shell_codeblocks(lines):
    """
    Processes shell code blocks to ensure [OPTIONS] is at the end of commands.
    """
    in_shell_block = False
    processed_lines = []
    code_block_start = re.compile(r"^```shell\s*$")
    code_block_end = re.compile(r"^```\s*$")

    for line in lines:
        if code_block_start.match(line):
            in_shell_block = True
            processed_lines.append(line)
            continue
        elif code_block_end.match(line):
            in_shell_block = False
            processed_lines.append(line)
            continue

        if in_shell_block:
            # Process the command line
            # Tokenize the line respecting shell quoting rules
            tokens = tokenize_command_line(line)
            if tokens and tokens[0] == "places":
                try:
                    options_index = tokens.index("[OPTIONS]")
                    # Remove [OPTIONS]
                    tokens.pop(options_index)
                    # Append [OPTIONS] at the end
                    tokens.append("[OPTIONS]")
                    # Reassemble the line
                    new_line = " ".join(tokens)
                    processed_lines.append(new_line)
                except ValueError:
                    # [OPTIONS] not found, keep line as is
                    processed_lines.append(line)
            else:
                processed_lines.append(line)
        else:
            processed_lines.append(line)

    return processed_lines


def tokenize_command_line(line):
    """
    Tokenizes a shell command line while respecting quoted substrings.
    """
    import shlex

    try:
        return shlex.split(line)
    except ValueError:
        # If there's a parsing error, return the line split by spaces
        return line.split()


def generate_docs():
    # Generate Sphinx documentation in Markdown format
    subprocess.run(
        ["sphinx-build", "-b", "markdown", ".", "./_build/markdown"], check=True
    )

    # Filter markdown sections and get filtered lines
    markdown_lines = filter_markdown_sections()

    # Convert options to table format
    table_content = []
    in_options = False
    in_arguments = False
    current_options = []
    current_arguments = []

    def parse_option(opt_str):
        # Split into short and long options
        parts = opt_str.split(", ")
        short = parts[0] if parts[0].startswith("-") else ""
        long_with_type = parts[1] if len(parts) > 1 else parts[0]

        # Extract type from long option if present
        type_match = re.search(r"<([^>]+)>", long_with_type) if long_with_type else None
        long = re.sub(r"<[^>]+>", "", long_with_type).strip() if long_with_type else ""
        type_info = f"<{type_match.group(1)}>" if type_match else ""

        return short.strip(), (long + " " + type_info).strip()

    def output_options_table(options):
        if options:
            result = []
            result.append("\n**Options**\n")
            result.append("| Short | Long Option | Description |")
            result.append("|-------|-------------|-------------|")
            for short, long, desc in options:
                result.append(f"| `{short}` | `{long}` | {desc} |")
            result.append("")
            return result
        return []

    def output_arguments_table(arguments):
        if arguments:
            result = []
            result.append("\n**Arguments**\n")
            result.append("| Argument | Required |")
            result.append("|----------|----------|")
            for arg, req in arguments:
                result.append(f"| `{arg}` | {req} |")
            result.append("")
            return result
        return []

    def wrap_in_details(content):
        result = []
        result.append("<details>")

        # Determine what sections are present
        has_options = any("**Options**" in line for line in content)
        has_arguments = any("**Arguments**" in line for line in content)

        # Create dynamic summary text
        summary_text = (
            "Options & Arguments"
            if has_options and has_arguments
            else "Options" if has_options else "Arguments"
        )

        result.append("\n***")
        result.append(f"\n<summary>{summary_text}</summary>\n")
        result.extend(content)
        result.append("***\n")
        result.append("</details>\n")
        return result

    for i, line in enumerate(markdown_lines):
        if line.strip() == "### Options":
            in_options = True
            in_arguments = False
            current_options = []
            # Start collecting options without adding the header
            continue

        elif line.strip() == "### Arguments":
            in_arguments = True
            in_options = False
            current_arguments = []
            continue

        # Rest of the processing logic
        if in_arguments:
            if (
                line.startswith("### ")
                and line[4:].strip().isupper()
                and not line.startswith("### Arguments")
            ):
                arg_name = line.replace("### ", "").strip()
                if i + 1 < len(markdown_lines):
                    requirement = markdown_lines[i + 1].strip()
                    is_required = "✅" if "Required" in requirement else "❌"
                    current_arguments.append((arg_name, is_required))
            elif line.startswith("##") or line.startswith("### Options"):
                # Output both tables wrapped in a single details block
                if current_options or current_arguments:
                    content = []
                    if current_options:
                        content.extend(output_options_table(current_options))
                    if current_arguments:
                        content.extend(output_arguments_table(current_arguments))
                    table_content.extend(wrap_in_details(content))
                    current_options = []
                    current_arguments = []
                in_arguments = False
                table_content.append(line)

        elif in_options:
            if line.startswith("### -"):
                option = line.replace("### ", "").strip()
                if i + 2 < len(markdown_lines):
                    description = markdown_lines[i + 2].strip()
                    short_opt, long_opt = parse_option(option)
                    current_options.append((short_opt, long_opt, description))
            elif line.startswith("##"):
                # Output both tables wrapped in a single details block
                if current_options or current_arguments:
                    content = []
                    if current_options:
                        content.extend(output_options_table(current_options))
                    if current_arguments:
                        content.extend(output_arguments_table(current_arguments))
                    table_content.extend(wrap_in_details(content))
                    current_options = []
                    current_arguments = []
                in_options = False
                table_content.append(line)
        else:
            table_content.append(line)

    # Handle any remaining tables at the end
    if current_options or current_arguments:
        content = []
        if current_options:
            content.extend(output_options_table(current_options))
        if current_arguments:
            content.extend(output_arguments_table(current_arguments))
        table_content.extend(wrap_in_details(content))

    filtered_content = "\n".join(table_content)

    # Update README.md
    with open("../README.md", "r") as f:
        readme_content = f.read()
        doc_section_start = "# places CLI Documentation"
        parts = readme_content.split(doc_section_start)

    with open("../README.md", "w") as f:
        f.write(parts[0])
        f.write(doc_section_start + "\n\n")
        f.write(filtered_content)


if __name__ == "__main__":
    generate_docs()

    # Delete the _build folder after successful creation
    shutil.rmtree("./_build")
