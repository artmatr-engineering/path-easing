import typer
import numpy as np
from gcodeparser import GcodeParser as gp
from manipulate_polyline import manipulate_polyline as mp
import sys
import json
from collections import Counter
from rich import print
from typing_extensions import Annotated
from typing import Optional
from pathlib import Path

params_default = {
    'start_shift': 1,
    'end_shift': 0,
    'start_extend': 5,
    'end_extend': 5,
    'start_extend_height': 4,
    'end_extend_height': 4,
    'start_pushthrough_inset': 2,
    'end_pushthrough_inset': 2,
    'start_pushthrough_z': -3,
    'end_pushthrough_z': -2
}

def parse_and_manipulate_file(filename, out_filename, params):
    ''''''
    # Read the gcode file
    with open(filename, 'r') as f:
        gcodelines = f.readlines() 

    gcodelines = [line.replace('\n', '') for line in gcodelines]
    
    lines = []
    for gcodeline in gcodelines:
        parsed = gp(gcodeline, include_comments=True).lines
        if len(parsed) > 0:
            lines.append(parsed[0])

    # Find the clearence and drawing heights
    z_moves  = []
    for i, line in enumerate(lines):
        # print(line)
        if 'Z' in line.params.keys():
            z_moves.append(line.params['Z'])
    z_cnt = Counter(z_moves).most_common()
    draw_height = min(z_cnt[0][0], z_cnt[1][0])
    clearence = max(z_cnt[0][0], z_cnt[1][0])
    print(f"Found a drawing height of {draw_height} and a clearence height of {clearence}")

    # Find and alter the drawing moves
    new_gcodes = []
    last_move = None
    iterating_through_drawing_moves = False
    for i, line in enumerate(lines):
        if iterating_through_drawing_moves == True:
            if last_move != line:
                continue
            else:
                iterating_through_drawing_moves = False
        if i > 0 and i < len(lines)-3:
            # See if the current move goes to the xy beginning of a drawing move
            if 'X' and 'Y' in line.params.keys() and line.command == ('G', 0):
                # See if the next move is a z move to the drawing height
                if 'Z' in lines[i+1].params.keys():
                    if lines[i+1].params['Z'] == draw_height:
                        iterating_through_drawing_moves = True
                        # If we got this far it means we have drawing moves after the next move
                        upcoming_draw_moves = [line]
                        for j, remaining_line in enumerate(lines[i+3:]):
                            if 'Z' in remaining_line.params.keys():
                                if remaining_line.params['Z'] == clearence:
                                    break
                                else:
                                    upcoming_draw_moves.append(remaining_line)
                            elif 'X' in remaining_line.params.keys() or 'Y' in remaining_line.params.keys():
                                upcoming_draw_moves.append(remaining_line)
                        move_start_idx = i + 1
                        move_end_idx = i + 2 + len(upcoming_draw_moves)
                        # print(f"Found a drawing move starting at line {move_start_idx+1} and ending at line {move_end_idx+1}")
                        upcoming_draw_vertices = np.array([[draw_move.params['X'], draw_move.params['Y']] for draw_move in upcoming_draw_moves])
                        manipulated_vertices = mp(upcoming_draw_vertices, params)
                        last_move = lines[move_end_idx]
                        new_drawing_codes = [
                            f"G0 X{manipulated_vertices[0][0]:.4f} Y{manipulated_vertices[0][1]:.4f}",
                            f"G{lines[i+1].command[1]} Z{params['start_extend_height']:.4f}",
                        ]
                        for vertex in manipulated_vertices:
                            new_drawing_codes.append(f"G1 X{vertex[0]:.4f} Y{vertex[1]:.4f} Z{vertex[2]:.4f}")
                        # new_drawing_codes.append(f"G{lines[i+1].command[1]} Z{params['end_extend_height']}")
                        new_gcodes.append(new_drawing_codes)
                    else:
                        # print(f'adding {gcodelines[i]}')
                        new_gcodes.append([gcodelines[i]])
                else:
                    # print(f'adding {gcodelines[i]}')
                    new_gcodes.append([gcodelines[i]])
            else:
                # print(f'adding {gcodelines[i]}')
                new_gcodes.append([gcodelines[i]])
        else:
            # print(f'adding {gcodelines[i]}')
            new_gcodes.append([gcodelines[i]])

    # Flatten the new_gcodes list
    new_gcodes = [item for sublist in new_gcodes for item in sublist]
    with open(out_filename, 'w') as f:
        f.write('\n'.join(new_gcodes))
    print(f"[bold green]Wrote the output to: [/bold green] {out_filename}")


# def main(filename: str, params_filename: str):
def main(
        gcode_filename: Annotated[Path, typer.Argument(help="The gcode file to parse")],
        gcode_filename_out: Annotated[Path, typer.Argument(help="The gcode file to write to")],
        params_filename: Annotated[Optional[Path], typer.Option(help="A json file containing the parameters for the manipulation")] = None,
        # params_filename: str = typer.Option('params.json', help="A json file containing the parameters for the manipulation"),
        start_shift: float = typer.Option(params_default['start_shift'], help="The amount to extend or shorten the start of the drawing moves"),
        end_shift: float = typer.Option(params_default['end_shift'], help="The amount to extend or shorten the end of the drawing moves"),
        start_extend: float = typer.Option(params_default['start_extend'], help="extension distance from the curve start for a (new) lead in point"),
        end_extend: float = typer.Option(params_default['end_extend'], help="extension distance from the curve end for a (new) lead out point"),
        start_extend_height: float = typer.Option(params_default['start_extend_height'], help="height of the (new) lead in move point"),
        end_extend_height: float = typer.Option(params_default['end_extend_height'], help="height of the (new) lead out move point"),
        start_pushthrough_inset: float = typer.Option(params_default['start_pushthrough_inset'], help="distance in from the curve start for a (new) push through point along the curve"),
        end_pushthrough_inset: float = typer.Option(params_default['end_pushthrough_inset'], help="distance in from the curve end for a (new) push through point along the curve"),
        start_pushthrough_z: float = typer.Option(params_default['start_pushthrough_z'], help="height of the (new) push through move point along the curve"),
        end_pushthrough_z: float = typer.Option(params_default['end_pushthrough_z'], help="height of the (new) push through move point along the curve"),
    ):
    """
    Parses a gcode file and eases the drawing moves

    Note: parameters can be provided in a json file, but will be overridden by command line arguments
    """

    # Load the params file if it was provided
    if params_filename is not None:
        try:
            with open(params_filename, 'r') as f:
                raw = f.read()
                params = json.loads(raw)
            for key in params_default.keys():
                if key not in params.keys():
                    print(f"[bold red]Your parameter file was formatted incorrectly[/bold red]")
                    print(f"Please provide a params file in json format like so:")
                    print(raw)
                    return
        except:
            print(f"[bold red]Your parameter file {params_filename} was not found![/bold red]")
            return
    else:
        params = params_default
    
    # Update the params from args if they are not default
    if start_shift != params_default['start_shift']:
        params['start_shift'] = start_shift
    if end_shift != params_default['end_shift']:
        params['end_shift'] = end_shift
    if start_extend != params_default['start_extend']:
        params['start_extend'] = start_extend
    if end_extend != params_default['end_extend']:
        params['end_extend'] = end_extend
    if start_extend_height != params_default['start_extend_height']:
        params['start_extend_height'] = start_extend_height
    if end_extend_height != params_default['end_extend_height']:
        params['end_extend_height'] = end_extend_height
    if start_pushthrough_inset != params_default['start_pushthrough_inset']:
        params['start_pushthrough_inset'] = start_pushthrough_inset
    if end_pushthrough_inset != params_default['end_pushthrough_inset']:
        params['end_pushthrough_inset'] = end_pushthrough_inset
    if start_pushthrough_z != params_default['start_pushthrough_z']:
        params['start_pushthrough_z'] = start_pushthrough_z
    if end_pushthrough_z != params_default['end_pushthrough_z']:
        params['end_pushthrough_z'] = end_pushthrough_z

    # Print the params
    print(f"[bold green]Easing the paths in your file [/bold green]{gcode_filename} [bold green] with the following parameters:[/bold green]")
    print(json.dumps(params, indent=4))
    
    parse_and_manipulate_file(gcode_filename, gcode_filename_out,  params)


if __name__ == "__main__":
    typer.run(main)